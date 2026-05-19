using System.Collections.Generic;
using System.Security.Cryptography;
using System.Text;

namespace ChaosOne.Audit
{
    public readonly struct VerificationResult
    {
        public readonly bool Valid;
        public readonly long FailedAtSequence;
        public readonly string FailureReason;

        public VerificationResult(bool valid, long failedAtSequence, string failureReason)
        {
            Valid = valid;
            FailedAtSequence = failedAtSequence;
            FailureReason = failureReason;
        }

        public static VerificationResult Ok => new(valid: true, failedAtSequence: 0, failureReason: null);

        public static VerificationResult Failed(long sequence, string reason) =>
            new(valid: false, failedAtSequence: sequence, failureReason: reason);
    }

    /// <summary>
    /// Walks an ordered list of audit log entries and recomputes each entry's
    /// hash to verify the chain is unbroken. Any mismatch or missing link is
    /// reported with the sequence number where verification failed.
    /// </summary>
    public static class AuditLogVerifier
    {
        public static VerificationResult Verify(IReadOnlyList<AuditLogEntry> entries)
        {
            if (entries == null || entries.Count == 0) return VerificationResult.Ok;

            var expectedPrevious = string.Empty;
            long expectedSequence = 0;

            foreach (var entry in entries)
            {
                expectedSequence++;

                if (entry.sequence != expectedSequence)
                {
                    return VerificationResult.Failed(
                        entry.sequence,
                        $"sequence gap: expected {expectedSequence}, got {entry.sequence}");
                }

                if (!string.Equals(entry.previous_hash ?? string.Empty, expectedPrevious))
                {
                    return VerificationResult.Failed(
                        entry.sequence,
                        "previous_hash does not match the prior entry's hash");
                }

                var recomputed = Recompute(entry);
                if (!string.Equals(entry.hash, recomputed))
                {
                    return VerificationResult.Failed(
                        entry.sequence,
                        "hash does not match recomputed digest");
                }

                expectedPrevious = entry.hash;
            }

            return VerificationResult.Ok;
        }

        private static string Recompute(AuditLogEntry entry)
        {
            var canonical =
                $"{entry.previous_hash}|{entry.sequence}|{entry.monotonic_ts:R}|{entry.event_type}|{entry.payload_json}";
            byte[] digest;
            using (var sha = SHA256.Create())
            {
                digest = sha.ComputeHash(Encoding.UTF8.GetBytes(canonical));
            }
            var sb = new StringBuilder(digest.Length * 2);
            foreach (var b in digest) sb.Append(b.ToString("x2"));
            return sb.ToString();
        }
    }
}
