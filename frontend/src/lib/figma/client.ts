/**
 * FigmaClient — Figma REST API Integration
 * ==========================================
 * Extracts design tokens, components, styles, and assets from Figma files.
 * Used by the design-to-code pipeline to keep the codebase in sync with Figma.
 *
 * API Docs: https://developers.figma.com/docs/rest-api/
 * Rate limit: 200 GET requests per minute
 *
 * Usage:
 *   const client = new FigmaClient(process.env.FIGMA_ACCESS_TOKEN!);
 *   const file = await client.getFile("YOUR_FILE_KEY");
 *   const variables = await client.getVariables("YOUR_FILE_KEY");
 */

const FIGMA_API_BASE = "https://api.figma.com/v1";

interface FigmaRequestOptions {
  method?: "GET" | "POST";
  body?: Record<string, unknown>;
}

export interface FigmaFile {
  name: string;
  lastModified: string;
  version: string;
  document: FigmaNode;
  components: Record<string, FigmaComponent>;
  styles: Record<string, FigmaStyle>;
}

export interface FigmaNode {
  id: string;
  name: string;
  type: string;
  children?: FigmaNode[];
  [key: string]: unknown;
}

export interface FigmaComponent {
  key: string;
  name: string;
  description: string;
  componentSetId?: string;
}

export interface FigmaStyle {
  key: string;
  name: string;
  styleType: "FILL" | "TEXT" | "EFFECT" | "GRID";
  description: string;
}

export interface FigmaVariable {
  id: string;
  name: string;
  key: string;
  variableCollectionId: string;
  resolvedType: "BOOLEAN" | "FLOAT" | "STRING" | "COLOR";
  valuesByMode: Record<string, unknown>;
  description: string;
  scopes: string[];
  codeSyntax: Record<string, string>;
}

export interface FigmaVariableCollection {
  id: string;
  name: string;
  modes: Array<{ modeId: string; name: string }>;
  defaultModeId: string;
  variableIds: string[];
}

export class FigmaClient {
  private token: string;
  private cache = new Map<string, { data: unknown; expiry: number }>();
  private requestCount = 0;
  private requestWindowStart = Date.now();

  constructor(token: string) {
    if (!token) throw new Error("FIGMA_ACCESS_TOKEN is required");
    this.token = token;
  }

  // ── Core Request Method ────────────────────────────────────────
  private async request<T>(path: string, options: FigmaRequestOptions = {}): Promise<T> {
    // Rate limiting: 200 req/min
    const now = Date.now();
    if (now - this.requestWindowStart > 60_000) {
      this.requestCount = 0;
      this.requestWindowStart = now;
    }
    if (this.requestCount >= 190) {
      const waitMs = 60_000 - (now - this.requestWindowStart) + 1000;
      await new Promise((r) => setTimeout(r, waitMs));
      this.requestCount = 0;
      this.requestWindowStart = Date.now();
    }

    // Cache check (5 min TTL)
    const cacheKey = `${options.method || "GET"}:${path}`;
    const cached = this.cache.get(cacheKey);
    if (cached && cached.expiry > Date.now()) {
      return cached.data as T;
    }

    const url = `${FIGMA_API_BASE}${path}`;
    const headers: Record<string, string> = {
      "X-Figma-Token": this.token,
      "Content-Type": "application/json",
    };

    let retries = 3;
    while (retries > 0) {
      try {
        this.requestCount++;
        const res = await fetch(url, {
          method: options.method || "GET",
          headers,
          body: options.body ? JSON.stringify(options.body) : undefined,
        });

        if (res.status === 429) {
          // Rate limited — wait and retry
          const retryAfter = parseInt(res.headers.get("Retry-After") || "30", 10);
          await new Promise((r) => setTimeout(r, retryAfter * 1000));
          retries--;
          continue;
        }

        if (!res.ok) {
          throw new Error(`Figma API ${res.status}: ${res.statusText}`);
        }

        const data = await res.json() as T;
        // Cache successful GET responses for 5 minutes
        if ((options.method || "GET") === "GET") {
          this.cache.set(cacheKey, { data, expiry: Date.now() + 5 * 60_000 });
        }
        return data;
      } catch (err) {
        retries--;
        if (retries === 0) throw err;
        await new Promise((r) => setTimeout(r, 2000));
      }
    }

    throw new Error("Figma API request failed after retries");
  }

  // ── File Endpoints ─────────────────────────────────────────────

  /** Get full file JSON */
  async getFile(fileKey: string, depth?: number): Promise<FigmaFile> {
    const params = depth ? `?depth=${depth}` : "";
    return this.request<FigmaFile>(`/files/${fileKey}${params}`);
  }

  /** Get specific nodes from a file */
  async getFileNodes(fileKey: string, nodeIds: string[]): Promise<{ nodes: Record<string, { document: FigmaNode }> }> {
    const ids = nodeIds.join(",");
    return this.request(`/files/${fileKey}/nodes?ids=${encodeURIComponent(ids)}`);
  }

  /** Get file metadata only (lightweight) */
  async getFileMeta(fileKey: string): Promise<{ file: { name: string; lastModified: string; version: string } }> {
    return this.request(`/files/${fileKey}/meta`);
  }

  // ── Component & Style Endpoints ────────────────────────────────

  /** Get all components in a file (returned inline with getFile) */
  async getComponents(fileKey: string): Promise<Record<string, FigmaComponent>> {
    const file = await this.getFile(fileKey, 1);
    return file.components;
  }

  /** Get all styles in a file (returned inline with getFile) */
  async getStyles(fileKey: string): Promise<Record<string, FigmaStyle>> {
    const file = await this.getFile(fileKey, 1);
    return file.styles;
  }

  // ── Variable Endpoints ─────────────────────────────────────────

  /** Get all local variables (design tokens) from a file */
  async getVariables(fileKey: string): Promise<{
    variables: Record<string, FigmaVariable>;
    variableCollections: Record<string, FigmaVariableCollection>;
  }> {
    const res = await this.request<{ meta: { variables: Record<string, FigmaVariable>; variableCollections: Record<string, FigmaVariableCollection> } }>(`/files/${fileKey}/variables/local`);
    return res.meta;
  }

  /** Create or update variables in a file */
  async postVariables(fileKey: string, payload: {
    variableCollections?: Array<{ action: "CREATE" | "UPDATE" | "DELETE"; id?: string; name?: string; initialModeId?: string }>;
    variableModes?: Array<{ action: "CREATE" | "UPDATE" | "DELETE"; id?: string; name?: string; variableCollectionId?: string }>;
    variables?: Array<{ action: "CREATE" | "UPDATE" | "DELETE"; id?: string; name?: string; variableCollectionId?: string; resolvedType?: string; [key: string]: unknown }>;
    variableModeValues?: Array<{ variableId: string; modeId: string; value: unknown }>;
  }): Promise<{ tempIdToRealId: Record<string, string> }> {
    const res = await this.request<{ meta: { tempIdToRealId: Record<string, string> } }>(`/files/${fileKey}/variables`, { method: "POST", body: payload as unknown as Record<string, unknown> });
    return res.meta;
  }

  // ── Image Export ───────────────────────────────────────────────

  /** Export nodes as images (SVG, PNG, JPG, PDF) */
  async getImages(fileKey: string, nodeIds: string[], options?: {
    format?: "svg" | "png" | "jpg" | "pdf";
    scale?: number;
    svgOutlineText?: boolean;
  }): Promise<Record<string, string>> {
    const ids = nodeIds.join(",");
    const format = options?.format || "svg";
    const scale = options?.scale || 1;
    const params = `ids=${encodeURIComponent(ids)}&format=${format}&scale=${scale}`;
    const res = await this.request<{ images: Record<string, string> }>(`/images/${fileKey}?${params}`);
    return res.images;
  }

  // ── Utility ────────────────────────────────────────────────────

  /** Test connection — returns user info */
  async testConnection(): Promise<{ id: string; handle: string; email: string }> {
    return this.request("/me");
  }

  /** Clear the request cache */
  clearCache(): void {
    this.cache.clear();
  }
}

// ── Design Token Extraction Helpers ──────────────────────────────

/** Convert Figma RGBA color to CSS hex */
export function figmaColorToHex(color: { r: number; g: number; b: number; a?: number }): string {
  const r = Math.round(color.r * 255);
  const g = Math.round(color.g * 255);
  const b = Math.round(color.b * 255);
  return `#${r.toString(16).padStart(2, "0")}${g.toString(16).padStart(2, "0")}${b.toString(16).padStart(2, "0")}`;
}

/** Convert Figma variable value to CSS custom property value */
export function figmaVariableToCss(variable: FigmaVariable, modeId: string): string | null {
  const value = variable.valuesByMode[modeId];
  if (value == null) return null;

  switch (variable.resolvedType) {
    case "COLOR": {
      const c = value as { r: number; g: number; b: number; a?: number };
      return figmaColorToHex(c);
    }
    case "FLOAT":
      return `${value}px`;
    case "STRING":
      return String(value);
    default:
      return String(value);
  }
}

/** Extract all color variables from a Figma file into CSS custom properties */
export function extractColorTokens(
  variables: Record<string, FigmaVariable>,
  collections: Record<string, FigmaVariableCollection>,
): Record<string, Record<string, string>> {
  const tokens: Record<string, Record<string, string>> = {};

  for (const variable of Object.values(variables)) {
    if (variable.resolvedType !== "COLOR") continue;

    const collection = collections[variable.variableCollectionId];
    if (!collection) continue;

    for (const mode of collection.modes) {
      const modeName = mode.name.toLowerCase();
      if (!tokens[modeName]) tokens[modeName] = {};

      const cssValue = figmaVariableToCss(variable, mode.modeId);
      if (cssValue) {
        const cssName = `--${variable.name.replace(/\//g, "-").replace(/\s+/g, "-").toLowerCase()}`;
        tokens[modeName][cssName] = cssValue;
      }
    }
  }

  return tokens;
}
