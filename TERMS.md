# SiteSpec API: Terms of Use

_Last updated: October 4, 2026_

These terms apply to your use of the SiteSpec API ("the API"). They add to the RapidAPI Terms of Service, which govern your account, subscription, billing, and refunds. By subscribing to or calling the API, you agree to these terms.

## 1. The service
SiteSpec returns site design and hazard information for a US location: seismic design values, FEMA flood zone, climate zone, design-storm rainfall, and wildfire exposure. It assembles this from public US government data sources (listed in section 3). SiteSpec is an independent service and is not affiliated with or endorsed by any government agency.

## 2. Data handling
- **No database of lookups.** We do not keep a database of the addresses or coordinates you submit. Results are held in a temporary in-memory cache (up to 24 hours) to speed up repeat requests, and are lost when the service restarts.
- **Operational logs.** Our hosting provider records request metadata: time, endpoint, status code, response time, network address, and the request URL, which includes the address or coordinates you send as query parameters. These logs are kept only as long as the hosting provider retains them. Do not send information in the `address` parameter beyond the address itself.
- **Data sent to government sources.** To answer a request, the address or coordinates you submit are forwarded to the public services listed in section 3. Their own policies apply to requests they receive. We do not send any other information about you or your account to them.
- **Location.** The API is hosted by Render in the United States. RapidAPI processes your requests as a proxy under its own privacy policy.

## 3. Data sources
- Address matching and county: US Census Bureau geocoder.
- Seismic design values: US Geological Survey (ASCE 7-22 and ASCE 7-16 web services).
- Flood zone: FEMA National Flood Hazard Layer.
- Climate zone: IECC climate zones by county, from US Department of Energy / PNNL data bundled with the API.
- Rainfall: NOAA Atlas 14 precipitation frequency estimates.
- Wildfire: USDA Forest Service Wildfire Risk to Communities (2024), accessed through the federal geoplatform service.

Source data can be out of date, incomplete, or temporarily unavailable. Each section of a response reports its own `status` so you can see when a source did not answer.

## 4. Screening data only; not professional advice
**The API provides informational screening data. It is not a site-specific study, an engineering or architectural design, an official flood determination, an insurance or lending decision, or legal advice.** Values may differ from those required by your local building department or authority having jurisdiction, from newer map revisions, and from conditions at the actual site (for example, soil conditions that change the seismic site class).

- Have a licensed professional verify any value before you use it for design, construction, permitting, insurance, lending, or purchase decisions.
- Do not use the API for emergency response or any life-safety decision.
- Wildfire values are raw indexes provided by the source without a documented unit scale. Use them for relative comparison only.
- Wind and snow loads are not provided.

You are responsible for how you use the data and for what you display to your own customers. If you show SiteSpec data to end users, we recommend you pass on a similar disclaimer.

## 5. Your responsibilities
- Use the API only for lawful purposes and only for locations and data you may lawfully look up.
- Do not attempt to bypass RapidAPI, exceed your plan's rate limits by technical means, or overload the service.
- Do not use the API to bulk-harvest results in order to republish or resell a copy of the dataset.
- Do not misrepresent SiteSpec data as an official government determination, or imply that any agency endorses your product.

## 6. Availability and changes
- The API is provided "as is" and "as available", with no uptime or service-level guarantee. It depends on third-party government services that may be slow, change format, or go offline without notice. Some may block requests or become unavailable, in which case the affected section returns `unavailable`.
- Endpoints under `/v1` will not have breaking changes without at least 30 days' notice on the RapidAPI listing. We may add new optional fields, sections, or endpoints at any time.
- Coverage is limited to the United States. Some sections have known gaps (for example, rainfall is not available where NOAA Atlas 14 does not cover).

## 7. Limitation of liability
To the maximum extent permitted by law, the provider is not liable for indirect, incidental, or consequential damages, or for losses resulting from reliance on the data, including construction, design, insurance, lending, or real-estate decisions. Total liability for any claim is limited to the amount you paid for the API in the 3 months before the claim.

## 8. Suspension
We may suspend access for violations of these terms, abuse, or activity that threatens the service's stability or other users.

## 9. Changes to these terms
We may update these terms. Material changes will be announced on the RapidAPI listing. Continuing to use the API after a change means you accept the updated terms.

## 10. Contact
Questions: use the Discussions tab on the RapidAPI listing, or email propeneprop@gmail.com.
