const fallbackSiteUrl = "http://localhost:3000";

export function getSiteUrl() {
  return new URL(process.env.FILEMINO_SITE_URL ?? fallbackSiteUrl);
}

export function getAbsoluteUrl(path: string) {
  return new URL(path, getSiteUrl()).toString();
}
