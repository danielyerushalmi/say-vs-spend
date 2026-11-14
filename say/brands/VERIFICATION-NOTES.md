# Online-share verification (2026-11-14, about 12:00 ET)

Rule used: PASS only if the company's own IR site says or shows sales are mostly through its own website/app. No percentage found = noted. Unreadable or bot-checked pages were skipped, not bypassed.

| id | pass | strength of evidence |
|---|---|---|
| hims | yes | strong: Online 98.4% vs Wholesale in IR-hosted 10-Q (6 months to 2025-06-30) |
| bark | yes | strong: Direct to Consumer 82.3% of FY2026 revenue (IR release table) |
| stitchfix | yes | medium: release says all Fixes are checked out in the app or on the website; no % |
| revolve | yes | medium: "e-commerce business model"; no % |
| thredup | yes | medium: "online resale platform"; no %; resale-as-a-service share unknown |
| petmeds | yes | medium: "national online pharmacy"; no %; phone orders not ruled out |
| lulus | no | no online % on IR page; wholesale growing |
| figs | yes | medium: FY2025 10-K says sales are "primarily through our direct-to-consumer (DTC) digital platform, consisting of our website, mobile app and B2B business (TEAMS)"; no %; rechecked 12:26 against frozen rule |
| flowers | no | online + telephonic + stores + wholesale; no own-site share |
| realreal | no | has retail stores; no channel split on IR pages |
| rtr | no | no online share stated |
| carparts | yes (marginal) | FY2025 10-K: online channel "primarily consists of our flagship ... website www.carparts.com, and mobile app"; also eBay/Amazon and wholesale; no % split; rechecked 12:26 |

Blocked or unreadable (stopped, no bypass): investors.hims.com (Cloudflare challenge), s202.q4cdn.com FIGS 10-K PDF (bot-check page), investor.therealreal.com (challenge on curl). Several IR pages that curl could not read returned normally through Scrapling plain requests.

Rent the Runway: IR release states "Revenue was $329.8 million" for FY2025 (ended 2026-01-31), so 329.8M is total revenue. The 43.8M figure is not.

CIKs for hims, revolve, stitchfix, thredup, lulus were not taken from company IR pages. Each was confirmed by matching the entity name returned by data.sec.gov (Hims & Hers Health, Revolve Group, Stitch Fix, ThredUp, Lulu's Fashion Lounge Holdings).
Stitch Fix revenue is FY2026 (ended 2026-08-01) and matches the IR release ($1,348,119K).

Recheck 12:26 (frozen rule): figs and carparts pass; lulus, flowers, realreal, rtr fail (b). 10-K quotes came from search-engine snippets of the sec.gov filing URLs because www.sec.gov returned 403 on the single request allowed; revenue re-verified from data.sec.gov for all six.
