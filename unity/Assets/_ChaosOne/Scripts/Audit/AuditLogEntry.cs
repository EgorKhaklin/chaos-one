using System;

namespace ChaosOne.Audit
{
    /// <summary>
    /// One row in the audit log. Serialized as JSON. The hash field is a
    /// SHA-256 over the JSON-canonical-form of (previous_hash || timestamp ||
    /// event_type || payload), giving an append-only Merkle chain. PQC
    /// signing arrives in milestone 6+.
    /// </summary>
    [Serializable]
    public sealed class AuditLogEntry
    {
        public long sequence;
        public double monotonic_ts;
        public string utc_iso;
        public string event_type;
        public string payload_json;
        public string previous_hash;
        public string hash;
    }
}
