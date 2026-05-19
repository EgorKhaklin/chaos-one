using System.IO;
using ChaosOne.Audit;
using NUnit.Framework;

namespace ChaosOne.Tests
{
    public sealed class AuditChainTests
    {
        private string tempPath;

        [SetUp]
        public void SetUp()
        {
            tempPath = Path.Combine(Path.GetTempPath(), $"chaos_audit_{System.Guid.NewGuid():N}.jsonl");
        }

        [TearDown]
        public void TearDown()
        {
            if (File.Exists(tempPath)) File.Delete(tempPath);
        }

        [Test]
        public void Empty_Log_Verifies_As_Ok()
        {
            File.WriteAllText(tempPath, string.Empty);
            var entries = AuditLogReader.Load(tempPath);
            var result = AuditLogVerifier.Verify(entries);
            Assert.That(result.Valid, Is.True);
        }

        [Test]
        public void Tampered_Payload_Fails_Verification()
        {
            // Hand-craft two valid entries, then corrupt the second's payload.
            const string firstHash = "0000000000000000000000000000000000000000000000000000000000000000";
            var firstEntry = new AuditLogEntry
            {
                sequence = 1,
                monotonic_ts = 0.0,
                utc_iso = "2025-01-01T00:00:00Z",
                event_type = "test_event",
                payload_json = "{\"k\":\"v\"}",
                previous_hash = string.Empty,
                hash = HashHelper.Compute(string.Empty, 1, 0.0, "test_event", "{\"k\":\"v\"}"),
            };
            var firstJson = UnityEngine.JsonUtility.ToJson(firstEntry);

            var secondEntry = new AuditLogEntry
            {
                sequence = 2,
                monotonic_ts = 1.0,
                utc_iso = "2025-01-01T00:00:01Z",
                event_type = "test_event",
                payload_json = "{\"k\":\"tampered\"}",
                previous_hash = firstEntry.hash,
                hash = HashHelper.Compute(firstEntry.hash, 2, 1.0, "test_event", "{\"k\":\"original\"}"),
            };
            var secondJson = UnityEngine.JsonUtility.ToJson(secondEntry);

            File.WriteAllText(tempPath, firstJson + "\n" + secondJson + "\n");

            var entries = AuditLogReader.Load(tempPath);
            var result = AuditLogVerifier.Verify(entries);

            Assert.That(result.Valid, Is.False);
            Assert.That(result.FailedAtSequence, Is.EqualTo(2));
            _ = firstHash;
        }
    }

    internal static class HashHelper
    {
        public static string Compute(string prev, long sequence, double monotonic, string type, string payload)
        {
            var canonical = $"{prev}|{sequence}|{monotonic:R}|{type}|{payload}";
            byte[] digest;
            using (var sha = System.Security.Cryptography.SHA256.Create())
            {
                digest = sha.ComputeHash(System.Text.Encoding.UTF8.GetBytes(canonical));
            }
            var sb = new System.Text.StringBuilder(digest.Length * 2);
            foreach (var b in digest) sb.Append(b.ToString("x2"));
            return sb.ToString();
        }
    }
}
