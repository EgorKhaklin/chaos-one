using System;
using System.Collections.Generic;
using System.IO;
using UnityEngine;

namespace ChaosOne.Audit
{
    /// <summary>
    /// Reads a JSONL audit log from disk and returns its entries in order.
    /// </summary>
    public static class AuditLogReader
    {
        public static IReadOnlyList<AuditLogEntry> Load(string path)
        {
            if (string.IsNullOrEmpty(path)) throw new ArgumentNullException(nameof(path));
            if (!File.Exists(path)) throw new FileNotFoundException("audit log not found", path);

            var lines = File.ReadAllLines(path);
            var entries = new List<AuditLogEntry>(lines.Length);

            foreach (var line in lines)
            {
                var trimmed = line.Trim();
                if (trimmed.Length == 0) continue;

                AuditLogEntry entry = null;
                try
                {
                    entry = JsonUtility.FromJson<AuditLogEntry>(trimmed);
                }
                catch (Exception parseEx)
                {
                    Debug.LogWarning($"audit log: skipping malformed line: {parseEx.Message}");
                    continue;
                }

                if (entry == null) continue;
                entries.Add(entry);
            }

            return entries;
        }
    }
}
