using ChaosOne.Audit;
using UnityEngine;
using UnityEngine.UIElements;

namespace ChaosOne.UI
{
    /// <summary>
    /// Loads an audit log file, verifies its hash chain, and renders entries
    /// in a scrollable list with the verification result at the top. Designed
    /// for the post-engagement review surface; designed for the board of
    /// inquiry as much as for the operator.
    /// </summary>
    [RequireComponent(typeof(UIDocument))]
    public sealed class AuditReelView : MonoBehaviour
    {
        [SerializeField] private string logPathOverride;
        [SerializeField] private bool autoLoadOnEnable = true;

        private Label statusLabel;
        private Label pathLabel;
        private ScrollView entryList;
        private Button loadButton;
        private TextField pathField;

        private void OnEnable()
        {
            var document = GetComponent<UIDocument>();
            UIDocumentLayout.FillPanel(document);
            var rv = document.rootVisualElement;
            if (rv == null) { enabled = false; return; }

            statusLabel = rv.Q<Label>("status");
            pathLabel = rv.Q<Label>("path");
            entryList = rv.Q<ScrollView>("entry-list");
            loadButton = rv.Q<Button>("btn-load");
            pathField = rv.Q<TextField>("path-input");

            if (loadButton != null)
            {
                loadButton.clicked += () => Load(pathField?.value);
            }

            if (autoLoadOnEnable)
            {
                Load(string.IsNullOrEmpty(logPathOverride) ? null : logPathOverride);
            }
        }

        public void Load(string path)
        {
            if (entryList == null) return;
            entryList.Clear();

            if (string.IsNullOrEmpty(path))
            {
                if (statusLabel != null) statusLabel.text = "no log path specified";
                if (pathLabel != null) pathLabel.text = "--";
                return;
            }

            if (pathLabel != null) pathLabel.text = path;

            try
            {
                var entries = AuditLogReader.Load(path);
                var verification = AuditLogVerifier.Verify(entries);

                if (statusLabel != null)
                {
                    statusLabel.text = verification.Valid
                        ? $"CHAIN VERIFIED · {entries.Count} entries"
                        : $"CHAIN BROKEN at seq {verification.FailedAtSequence}: {verification.FailureReason}";

                    statusLabel.RemoveFromClassList("audit-status--ok");
                    statusLabel.RemoveFromClassList("audit-status--broken");
                    statusLabel.AddToClassList(verification.Valid ? "audit-status--ok" : "audit-status--broken");
                }

                foreach (var entry in entries)
                {
                    entryList.Add(BuildRow(entry));
                }
            }
            catch (System.Exception ex)
            {
                if (statusLabel != null)
                {
                    statusLabel.text = $"failed to load: {ex.Message}";
                    statusLabel.AddToClassList("audit-status--broken");
                }
            }
        }

        private static VisualElement BuildRow(AuditLogEntry entry)
        {
            var row = new VisualElement();
            row.AddToClassList("audit-row");

            var seq = new Label($"#{entry.sequence:D4}");
            seq.AddToClassList("audit-row__seq");

            var time = new Label(entry.utc_iso ?? "--");
            time.AddToClassList("audit-row__time");

            var type = new Label(entry.event_type ?? "?");
            type.AddToClassList("audit-row__type");

            var payload = new Label(entry.payload_json ?? "{}");
            payload.AddToClassList("audit-row__payload");
            payload.style.whiteSpace = WhiteSpace.NoWrap;

            row.Add(seq);
            row.Add(time);
            row.Add(type);
            row.Add(payload);
            return row;
        }
    }
}
