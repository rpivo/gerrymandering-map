/** Where feedback, corrections and ideas go: forwarded by Cloudflare Email Routing. */
export const FEEDBACK_EMAIL = "hello@gerrymandermap.us";

/** The repo's issue forms (feature requests and data errors), for people with GitHub. */
export const ISSUES_URL = "https://github.com/rpivo/gerrymandering-map/issues/new/choose";

/**
 * Build an email link for reporting a problem with one page.
 * @param page What the page is about, such as "TX-35".
 * @returns A mailto link whose subject names the page.
 */
export function reportLink(page: string): string {
  return `mailto:${FEEDBACK_EMAIL}?subject=${encodeURIComponent(`${page} on Gerrymander Map`)}`;
}
