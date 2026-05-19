using System.Collections.Generic;
using ChaosOne.Core;
using ChaosOne.Decisions;
using ChaosOne.Threats;
using UnityEngine;
using UnityEngine.UIElements;

namespace ChaosOne.UI
{
    /// <summary>
    /// Bottom-anchored slow-scrolling event ticker. Subscribes to a curated
    /// set of events and emits one short line per event into a capped queue.
    /// Not for shouting. Audit-relevant context only; threats render on the
    /// Stage, decisions render on the Decisions Panel.
    /// </summary>
    [RequireComponent(typeof(UIDocument))]
    public sealed class CalmChannel : MonoBehaviour
    {
        [SerializeField] private int maxEntries = 8;

        private VisualElement entryList;
        private readonly Queue<VisualElement> entries = new();

        private void OnEnable()
        {
            var document = GetComponent<UIDocument>();
            UIDocumentLayout.FillPanel(document);
            var rv = document.rootVisualElement;
            if (rv == null) { enabled = false; return; }

            entryList = rv.Q<VisualElement>("calm-channel-list");

            EventBus.Subscribe<ModeChanged>(OnModeChanged);
            EventBus.Subscribe<ROEEnvelopeChanged>(OnRoeChanged);
            EventBus.Subscribe<COAProposed>(OnCoaProposed);
            EventBus.Subscribe<COAAuthorized>(OnCoaAuthorized);
            EventBus.Subscribe<COAObjected>(OnCoaObjected);
            EventBus.Subscribe<COAExpired>(OnCoaExpired);
            EventBus.Subscribe<TrackSpawned>(OnTrackSpawned);
            EventBus.Subscribe<TrackDestroyed>(OnTrackDestroyed);
        }

        private void OnDisable()
        {
            EventBus.Unsubscribe<ModeChanged>(OnModeChanged);
            EventBus.Unsubscribe<ROEEnvelopeChanged>(OnRoeChanged);
            EventBus.Unsubscribe<COAProposed>(OnCoaProposed);
            EventBus.Unsubscribe<COAAuthorized>(OnCoaAuthorized);
            EventBus.Unsubscribe<COAObjected>(OnCoaObjected);
            EventBus.Unsubscribe<COAExpired>(OnCoaExpired);
            EventBus.Unsubscribe<TrackSpawned>(OnTrackSpawned);
            EventBus.Unsubscribe<TrackDestroyed>(OnTrackDestroyed);
        }

        private void OnModeChanged(ModeChanged evt) =>
            Append($"MODE {LetterFor(evt.Current)} — {NameFor(evt.Current)}");

        private void OnRoeChanged(ROEEnvelopeChanged evt) =>
            Append($"ROE {evt.PreviousId} → {evt.CurrentId}");

        private void OnCoaProposed(COAProposed evt) =>
            Append($"COA proposed {evt.Coa.Id} ({(evt.Coa.IsRecommended ? "RECOMMENDED" : "alternative")})");

        private void OnCoaAuthorized(COAAuthorized evt) =>
            Append($"COA authorized {evt.Coa.Id} ({SourceLabel(evt.Source)})");

        private void OnCoaObjected(COAObjected evt) =>
            Append($"COA objected {evt.Coa.Id} — {evt.Reason}");

        private void OnCoaExpired(COAExpired evt) =>
            Append($"COA expired {evt.Coa.Id}");

        private void OnTrackSpawned(TrackSpawned evt) =>
            Append($"track acquired {evt.Track.Id} ({evt.Track.Archetype.ClassKind})");

        private void OnTrackDestroyed(TrackDestroyed evt) =>
            Append($"track lost {evt.Track.Id}");

        private void Append(string text)
        {
            if (entryList == null) return;

            var entry = new Label(text);
            entry.AddToClassList("calm-channel__entry");
            entryList.Add(entry);
            entries.Enqueue(entry);

            while (entries.Count > maxEntries)
            {
                var oldest = entries.Dequeue();
                entryList.Remove(oldest);
            }
        }

        private static string LetterFor(OperationalMode mode) => mode switch
        {
            OperationalMode.Nominal => "A",
            OperationalMode.SensorDegraded => "B",
            OperationalMode.CommsDegraded => "C",
            OperationalMode.CyberSuspect => "D",
            OperationalMode.AdvisoryOnly => "E",
            OperationalMode.PrePositionedAutonomous => "F",
            _ => "?",
        };

        private static string NameFor(OperationalMode mode) => mode switch
        {
            OperationalMode.Nominal => "NOMINAL",
            OperationalMode.SensorDegraded => "SENSOR DEGRADED",
            OperationalMode.CommsDegraded => "COMMS DEGRADED",
            OperationalMode.CyberSuspect => "CYBER-SUSPECT",
            OperationalMode.AdvisoryOnly => "ADVISORY ONLY",
            OperationalMode.PrePositionedAutonomous => "AUTONOMOUS FIRE",
            _ => "UNKNOWN",
        };

        private static string SourceLabel(AuthorizationSource source) => source switch
        {
            AuthorizationSource.Operator => "operator",
            AuthorizationSource.OperatorWithCoSign => "operator + co-sign",
            AuthorizationSource.AutoExpire => "auto on expiry",
            AuthorizationSource.AutoAuthorizedByROE => "auto under ROE",
            _ => "?",
        };
    }
}
