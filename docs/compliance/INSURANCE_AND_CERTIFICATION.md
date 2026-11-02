# Insurance and certification — what to get, in what order (DRAFT)

## Insurance (buy before the first paying customer)
| Cover | Why | Notes |
|---|---|---|
| **Technology professional indemnity / errors & omissions**, with a **medical-software** extension | The main exposure: a claim that the software contributed to harm | Disclose decision-support honestly; ask that the Clinical Lead and Pharmacist are covered as advisers |
| **Cyber liability** | Breach response costs, notification, regulatory proceedings, restoration | Even for on-premise: your support access and update channel are attack paths |
| **General / public liability, directors' & officers'** | Ordinary business | — |
| Customers' own **doctor indemnity** | Not yours | State in the contract that clinics keep their own |

Brief a broker with: the intended-use statement, the architecture summary, this compliance pack, the hazard log and the incident procedure.

## Certification (worth the money, in order)
1. **None needed to start** beyond the practical controls already built. Do the next three before you scale.
2. **Independent penetration test** of the product and the installer (days; lowest cost, highest sales value). Fix, retest, keep the letter.
3. **ISO/IEC 27001** (information security) — what hospital chains and larger groups ask for. 6–12 months for a small company; scope it to the vendor's own support and release process.
4. **ISO 13485** (medical-device quality management) and **IEC 62304** lifecycle — only if the regulatory opinion says the decision-support features are a device. The evidence file in `DEVICE_REGULATORY_POSITION.md` is the starting point.
5. **ABDM / NHCX alignment** if customers want national health-stack integration — a product decision, not a certificate.
6. SOC 2 is mainly relevant for cloud/SaaS; skip for an on-premise product unless exporting to buyers who require it.

## Order of operations
Insurance quote → regulatory classification opinion → penetration test → design-partner clinic evaluation → sign-off by Clinical Lead and Pharmacist → first paying customer → ISO 27001 → (if required) ISO 13485.
