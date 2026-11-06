import { experimental_AstroContainer as AstroContainer } from "astro/container";
import { describe, expect, it } from "vitest";

import Base from "../layouts/Base.astro";
import DistrictPage from "../pages/[state]/[district].astro";
import Methodology from "../pages/methodology.astro";
import { getDistrict } from "./data";
import { FEEDBACK_EMAIL, ISSUES_URL, reportLink } from "./feedback";

const text = (html: string) => html.replace(/<[^>]+>/g, " ").replace(/&#39;/g, "'").replace(/\s+/g, " ");

describe("feedback links", () => {
  it("builds an email link with the page named in the subject", () => {
    expect(FEEDBACK_EMAIL).toBe("hello@gerrymandermap.us");
    expect(reportLink("TX-35")).toBe("mailto:hello@gerrymandermap.us?subject=TX-35%20on%20Gerrymander%20Map");
  });

  it("puts the email address and the GitHub issue forms in every page's footer", async () => {
    const container = await AstroContainer.create();
    const html = await container.renderToString(Base, { props: { title: "x", description: "x" } });
    const footer = html.slice(html.indexOf('<footer class="site-footer"'), html.indexOf("</footer>"));
    expect(footer).toMatch(/<a href="mailto:hello@gerrymandermap\.us"[^>]*>hello@gerrymandermap\.us<\/a>/);
    expect(footer).toContain(`href="${ISSUES_URL}"`);
    expect(text(footer)).toContain("Feedback or ideas?");
    // Astro drops a line break before a link, so the space must be written out.
    expect(footer.replace(/<[^>]+>/g, "")).toMatch(/, or suggest a feature on GitHub\./);
  });

  it("lets a district page's reader report a problem with that district", async () => {
    const container = await AstroContainer.create();
    const html = await container.renderToString(DistrictPage, { props: { district: getDistrict("TX-35") } });
    const start = html.indexOf('class="report"');
    expect(start).toBeGreaterThan(-1); // anchor: the line rendered
    const line = html.slice(start, html.indexOf("</p>", start));
    expect(line).toContain(`href="${reportLink("TX-35")}"`);
    expect(text(line)).toContain("Spot a problem with this district?");
  });

  it("explains on the methodology page how to send corrections and ideas", async () => {
    const container = await AstroContainer.create();
    const html = await container.renderToString(Methodology);
    expect(html).toMatch(/<h2[^>]*id="feedback"/);
    expect(html).toContain('href="mailto:hello@gerrymandermap.us"');
    expect(html).toContain(`href="${ISSUES_URL}"`);
  });
});
