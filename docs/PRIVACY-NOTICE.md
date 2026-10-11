# Institutional notice template · v1

FaceIQ processes a student's name, ERP ID, academic enrollment details, uploaded photograph and derived face template solely for attendance in authorized courses. Authorized administrators manage registrations; assigned faculty operate class sessions. Students with accounts may view their own academic records.

Face recognition is optional. The institution must offer a manual attendance method without punitive treatment for declining biometric processing. Registration requires an enrollment identity check; a name and photo are not identity proof by themselves.

Before collecting photographs, the institution must supply its controller identity, contact, approved legal basis, retention periods, complaint route, and consent withdrawal process. This application does not itself determine legal compliance or the validity of consent. Administrators should record consent only after the institutional process is complete.

Photos and templates are encrypted at rest in the database; the encryption key is maintained separately. Authenticated staff can access photos only within their permitted scope. Templates are never returned through the API. Live webcam frames are processed in memory and are not saved as images or video by the application. Recognition events retain timestamps, statuses, cosine scores and resolved student IDs when available.

Withdrawal or deactivation deletes photographs and template payloads from the live database. Academic attendance and audit history remain retained under institutional policy. Old database backups may still contain encrypted data until their separate backup retention expires. Encryption is not an erasure guarantee for copied backups. The institution must handle backup expiry and legal hold requirements explicitly.

Configured template retention defaults to 365 days and event retention to 30 days. The institution must schedule the cleanup command; expired templates are excluded from automatic recognition even before cleanup. Renew consent and re-enroll if needed. Academic records have no automatic deletion in this version.

No emotion inference, student profiling, or unrelated surveillance is implemented. Liveness detection is unavailable. Face matching is fallible and can be fooled by photos, displays and replay; an appropriate human verification process is essential for consequential attendance decisions.
