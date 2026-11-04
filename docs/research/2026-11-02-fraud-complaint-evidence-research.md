# Research: fraud-complaint evidence for Indian banks

Date: 2026-11-02. Method: 17 web searches and 4 page fetches, cross-checked claim by claim.
Confidence is High when three or more independent sources agree, Medium for two or for
consistent vendor sources, Low for one source or none.

## Question
The starting brief pitched a "Return Fraud Intelligence Platform" built on the claim that "RBI's
2026 liability rules require banks to justify every dispute decision within 45 days with an
auditable chain of evidence". Is that true, where is the real gap, and what sells?

## Verdict
The premise is half right. The RBI rules are real but cover fraud complaints ("fraudulent
electronic banking transactions"), not returns or merchant disputes. The real gap is the bank's
burden of proof on those complaints: the bank must prove customer liability within 45 days and
holds only its own logs. The buyer is the bank. Return-fraud signals are one source of evidence,
not the product.

## Claim check
| Claim in the brief | Finding | Confidence |
|---|---|---|
| "RBI 2026 liability rules" | Real: RBI/2026-27/167 to /173, issued 24 Jun 2026, for transactions from 1 Jan 2027 | High |
| "Justify every dispute decision within 45 days" | Fraud complaints only: 45 calendar days domestic, 60 cross-border | High |
| Bank carries the burden of proof | Yes, since the 2017 circular; 2026 adds itemised bank and customer negligence definitions | High |
| The rules cover return fraud or merchant disputes | No. Scope is third-party fraud, coercion and unauthorised transactions. Gateways and aggregators appear only as sources of a "third-party breach" | High |
| Return fraud reaches the bank | Mostly not: about 60% of Indian e-commerce orders are cash on delivery | Medium |
| "Retailers lose crores" in India | No sourced India figure. US: $101B (2023, NRF/Appriss), about $103B (2024, Appriss/Deloitte) | Low (India) |
| X-ray in-box check in about 3 s | Exists (Clarity / ReturnPro, 3.2 s); vendor claim, hardware, US | Medium |
| EXIF as a fraud signal | Weak: AI-faked damage photos are documented and inpainting defeats whole-image checks | Medium |
| Cross-institution hash registry | RBI's DPIP Smart Registry live with 8 banks since 1 Sep 2026 | Medium |
| Behavioural biometrics at claim time | DPDP is consent-based; the s.17(1)(c) offence-prevention exemption may cover private fraud work but is unsettled; in force 13 May 2027 | Medium |

## The RBI 2026 directions in numbers
| Rule | Value |
|---|---|
| Applies to | Electronic banking transactions on or after 1 Jan 2027 |
| Acknowledgement | Immediately, with a complaint number |
| Zero liability, third-party breach | Reported within 5 calendar days |
| Zero liability, bank negligence | Regardless of reporting time |
| Customer negligence | Customer bears the loss until reported, the bank after |
| Shadow reversal, credit card | Within 5 calendar days of notification |
| Resolution | Within 45 days domestic, 60 cross-border |
| Compensation | Customer-negligence loss up to ₹50,000; min(85% of net loss, ₹25,000); once in a lifetime; paid within 5 days of the completed form; frauds in the first year only |
| Compensation split | Domestic RBI 65 : customer bank 10 : beneficiary bank 10; cross-border RBI 65 : customer bank 20 |
| Alerts | SMS for every EBT above ₹500 |
| Records | Kept two years after the compensation scheme closes |

The beneficiary bank's share means money landing in mule accounts now costs the bank that holds
them, which ties complaint handling to MuleCatch's mule detection.

## Market and pricing
| Player | What it does | Pricing | India |
|---|---|---|---|
| Chargeflow | Chargeback automation | 25% of recovered (published) | No |
| Justt | Chargeback automation | Success fee; 35% claimed by a competitor, unverified | No |
| Signifyd, Riskified, Forter | Pre-authorisation screening with guarantees | % of approved GMV, custom | Limited |
| Razorpay | Dispute team plus Agent Studio AI dispute agent | Bundled | Yes |
| PayU | Manual network portals, SQL-built evidence | Bundled | Yes |
| ClickPost | Returns with SKU-mismatch flags | Usage-based, unpublished | Yes |
| Return Prime (GoKwik) | Shopify returns app | Tiered | Yes |

Visa Compelling Evidence 3.0 solves merchant-to-issuer evidence only for Visa reason code 10.4.
Nothing equivalent covers UPI plus cards in India.

## Decision
- Buyer: banks. The user sells and pitches directly.
- Product: a Fraud Complaint Desk inside MuleCatch (see
  `docs/superpowers/specs/2026-11-02-fraud-complaint-desk-design.md`).
- Deferred: X-ray, own hash registry, behavioural biometrics, mobile capture app.

## Not verified
- The RBI circular PDF itself (three secondary sources agree on the numbers).
- NPCI evidence rules for UPI "goods not received" disputes.
- Whether WhatsApp strips EXIF.
- How many false "not me" complaints Indian banks receive.

## Sources
- [MediaNama: final directions, effective 2027](https://www.medianama.com/2026/06/223-rbi-final-amendment-directions-limiting-customer-liability-digital-transactions-effect-2027/)
- [CorpLawUpdates: RBI/2026-27/167–173](https://www.corplawupdates.in/updates/rbi-fraudulent-ebt-customer-protection-compensation-directions)
- [ELP Law](https://elplaw.in/leadership/rbi-tightens-customer-protection-framework-for-fraudulent-electronic-banking-transactions-2/)
- [The Bar Bulletin: para 76K](https://thebarbulletin.com/rbi-2026-directions-customer-liability-bank-fraud/)
- [Moneylife: 2017 burden of proof](https://www.moneylife.in/article/moneylife-tweetmorcha-banksebachao-impact-rbi-limits-customer-liability-in-digital-transaction/50999.html)
- [MediaNama: DPIP Smart Registry live](https://www.medianama.com/2026/09/223-dpip-smart-registry-fraud-prevention/)
- [Business Standard: DPIP](https://www.business-standard.com/industry/banking/rbi-banks-to-launch-dpip-platform-to-combat-rising-digital-payment-frauds-125062200370_1.html)
- [Razorpay: cash on delivery](https://razorpay.com/blog/cash-on-delivery/)
- [Retail Dive: $101B return fraud](https://www.retaildive.com/news/retailers-took-back-743b-in-returns-last-year-with-101b-lost-to-fraud-n/703516/)
- [Appriss 2024 returns report](https://apprissretail.com/resources/2024-consumer-returns-report/)
- [Checkout.com: Visa CE 3.0](https://www.checkout.com/blog/visa-compelling-evidence-3-0)
- [Chargeflow billing](https://help.chargeflow.io/en/articles/15244894-when-and-how-does-chargeflow-charge-me)
- [Chargeback.io on Justt](https://www.chargeback.io/nl/blog/best-justt-alternatives)
- [Razorpay chargebacks](https://razorpay.com/blog/how-razorpay-helps-you-to-handle-chargebacks/)
- [Razorpay Agent Studio](https://razorpay.com/blog/agent-studio-ai-agents-by-razorpay)
- [ClickPost vs Return Prime](https://www.clickpost.ai/blog/top-10-best-return-prime-competitors-alternatives)
- [ReturnPro X-ray](https://www.returnpro.com/company/news-events/news/x-rays-and-ai-are-helping-retailers-catch-fraudulent-returns)
- [OECD AI incident: fake damage photos](https://oecd.ai/en/incidents/2025-08-30-db88)
- [Switchlabs: inpainting](https://www.switchlabs.dev/post/ai-faked-damage-photos-playbook)
- [Google: Pixel C2PA](https://blog.google/security/pixel-android-trusted-images-c2pa-content-credentials/)
- [DPDP section 17](https://www.dpdpa.com/dpdpa2023/chapter-4/section17.html)
- [Cyril Amarchand: s.17(1)(c)](https://disputeresolution.cyrilamarchandblogs.com/2025/01/internal-investigations-under-the-digital-personal-data-protection-act-2023/)
- [AZB: DPDP phases](https://www.azbpartners.com/bank/indias-digital-personal-data-protection-act-phased-rollout-and-key-compliance-milestones/)
