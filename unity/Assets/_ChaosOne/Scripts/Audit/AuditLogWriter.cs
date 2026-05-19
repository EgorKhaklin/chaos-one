using System;
using System.IO;
using System.Security.Cryptography;
using System.Text;
using ChaosOne.Core;
using ChaosOne.Decisions;
using ChaosOne.Threats;
using UnityEngine;

namespace ChaosOne.Audit
{
    /// <summary>
    /// Append-only, hash-chained event log. Subscribes to a curated set of
    /// events; each event becomes one JSONL line with a SHA-256 hash chaining
    /// it to the previous line. The log file is grouped under one engagement
    /// directory, named with a timestamp at scene boot, so concurrent runs
    /// don't collide.
    ///
    /// The chain is sufficient for tamper-evidence under integrity assumptions;
    /// adding PQC signatures (ML-DSA via liboqs) is the milestone-6 hardening
    /// step. Until then, the chain hash itself is the integrity surface.
    /// </summary>
    public sealed class AuditLogWriter : MonoBehaviour
    {
        [SerializeField] private bool enableAudit = true;
        [SerializeField] private string engagementLabel = "engagement";

        private string logPath;
        private string previousHash = string.Empty;
        private long sequence;
        private readonly object writeLock = new();

        public string LogPath => logPath;

        private void Awake()
        {
            if (!enableAudit) return;
            ServiceRegistry.Register(this);

            var stamp = DateTime.UtcNow.ToString("yyyyMMdd_HHmmss");
            var directory = Path.Combine(Application.persistentDataPath, "audit", $"{engagementLabel}_{stamp}");
            Directory.CreateDirectory(directory);
            logPath = Path.Combine(directory, "log.jsonl");

            File.WriteAllText(logPath, string.Empty);
            Append("audit_begin", $"{{\"label\":\"{engagementLabel}\"}}");
        }

        private void OnEnable()
        {
            if (!enableAudit) return;

            EventBus.Subscribe<ModeChanged>(OnModeChanged);
            EventBus.Subscribe<ROEEnvelopeChanged>(OnRoeChanged);
            EventBus.Subscribe<COAProposed>(OnCoaProposed);
            EventBus.Subscribe<COAAuthorized>(OnCoaAuthorized);
            EventBus.Subscribe<COAObjected>(OnCoaObjected);
            EventBus.Subscribe<COAExpired>(OnCoaExpired);
            EventBus.Subscribe<TrackSpawned>(OnTrackSpawned);
            EventBus.Subscribe<TrackStateChanged>(OnTrackStateChanged);
            EventBus.Subscribe<TrackDestroyed>(OnTrackDestroyed);
            EventBus.Subscribe<AdversaryPlaybookUpdated>(OnPlaybookUpdated);
        }

        private void OnDisable()
        {
            if (!enableAudit) return;

            EventBus.Unsubscribe<ModeChanged>(OnModeChanged);
            EventBus.Unsubscribe<ROEEnvelopeChanged>(OnRoeChanged);
            EventBus.Unsubscribe<COAProposed>(OnCoaProposed);
            EventBus.Unsubscribe<COAAuthorized>(OnCoaAuthorized);
            EventBus.Unsubscribe<COAObjected>(OnCoaObjected);
            EventBus.Unsubscribe<COAExpired>(OnCoaExpired);
            EventBus.Unsubscribe<TrackSpawned>(OnTrackSpawned);
            EventBus.Unsubscribe<TrackStateChanged>(OnTrackStateChanged);
            EventBus.Unsubscribe<TrackDestroyed>(OnTrackDestroyed);
            EventBus.Unsubscribe<AdversaryPlaybookUpdated>(OnPlaybookUpdated);
        }

        private void OnDestroy()
        {
            if (!enableAudit) return;
            Append("audit_end", "{}");
            ServiceRegistry.Unregister<AuditLogWriter>();
        }

        private void OnModeChanged(ModeChanged evt) =>
            Append("mode_changed", $"{{\"previous\":\"{evt.Previous}\",\"current\":\"{evt.Current}\"}}");

        private void OnRoeChanged(ROEEnvelopeChanged evt) =>
            Append("roe_envelope_changed", $"{{\"previous\":\"{Escape(evt.PreviousId)}\",\"current\":\"{Escape(evt.CurrentId)}\"}}");

        private void OnCoaProposed(COAProposed evt) =>
            Append("coa_proposed", $"{{\"id\":\"{Escape(evt.Coa.Id)}\",\"headline\":\"{Escape(evt.Coa.Headline)}\",\"recommended\":{(evt.Coa.IsRecommended ? "true" : "false")},\"countdown\":{evt.Coa.CountdownSeconds}}}");

        private void OnCoaAuthorized(COAAuthorized evt) =>
            Append("coa_authorized", $"{{\"id\":\"{Escape(evt.Coa.Id)}\",\"source\":\"{evt.Source}\"}}");

        private void OnCoaObjected(COAObjected evt) =>
            Append("coa_objected", $"{{\"id\":\"{Escape(evt.Coa.Id)}\",\"reason\":\"{Escape(evt.Reason)}\"}}");

        private void OnCoaExpired(COAExpired evt) =>
            Append("coa_expired", $"{{\"id\":\"{Escape(evt.Coa.Id)}\"}}");

        private void OnTrackSpawned(TrackSpawned evt) =>
            Append("track_spawned", $"{{\"id\":\"{Escape(evt.Track.Id)}\",\"class\":\"{evt.Track.Archetype.ClassKind}\"}}");

        private void OnTrackStateChanged(TrackStateChanged evt) =>
            Append("track_state_changed", $"{{\"id\":\"{Escape(evt.Track.Id)}\",\"previous\":\"{evt.Previous}\",\"current\":\"{evt.Current}\"}}");

        private void OnTrackDestroyed(TrackDestroyed evt) =>
            Append("track_destroyed", $"{{\"id\":\"{Escape(evt.Track.Id)}\"}}");

        private void OnPlaybookUpdated(AdversaryPlaybookUpdated evt) =>
            Append("adversary_playbook_updated", $"{{\"cost_imposition_index\":{evt.Distribution.CostImpositionIndex},\"hypothesis_count\":{evt.Distribution.Hypotheses.Count}}}");

        private void Append(string eventType, string payloadJson)
        {
            if (string.IsNullOrEmpty(logPath)) return;

            lock (writeLock)
            {
                var entry = new AuditLogEntry
                {
                    sequence = ++sequence,
                    monotonic_ts = Time.realtimeSinceStartupAsDouble,
                    utc_iso = DateTime.UtcNow.ToString("o"),
                    event_type = eventType,
                    payload_json = payloadJson,
                    previous_hash = previousHash,
                };
                entry.hash = ComputeHash(entry);
                previousHash = entry.hash;

                var json = JsonUtility.ToJson(entry);
                File.AppendAllText(logPath, json + "\n");
            }
        }

        private static string ComputeHash(AuditLogEntry entry)
        {
            var canonical =
                $"{entry.previous_hash}|{entry.sequence}|{entry.monotonic_ts:R}|{entry.event_type}|{entry.payload_json}";
            var bytes = Encoding.UTF8.GetBytes(canonical);
            var digest = SHA256.HashData(bytes);
            var sb = new StringBuilder(digest.Length * 2);
            foreach (var b in digest) sb.Append(b.ToString("x2"));
            return sb.ToString();
        }

        private static string Escape(string value)
        {
            if (string.IsNullOrEmpty(value)) return string.Empty;
            return value.Replace("\\", "\\\\").Replace("\"", "\\\"");
        }
    }
}
