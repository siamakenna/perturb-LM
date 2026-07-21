import type { SearchProvider, SearchResponse } from "./types";

export class ModelSearchProvider implements SearchProvider {
  async search(): Promise<SearchResponse> {
    throw new Error(
      "ModelSearchProvider is intentionally unimplemented until the real benchmark backend exists.",
    );
  }
}
