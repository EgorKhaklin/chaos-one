using ChaosOne.Core;
using ChaosOne.Threats;
using UnityEngine;
using UnityEngine.UIElements;

namespace ChaosOne.UI
{
    /// <summary>
    /// Subscribes to selection and update events and renders the active track's
    /// kinematic snapshot into a UI Toolkit panel. Hidden when nothing selected.
    /// </summary>
    [RequireComponent(typeof(UIDocument))]
    public sealed class TrackInfoPanel : MonoBehaviour
    {
        private VisualElement root;
        private Label trackIdLabel;
        private Label trackClassLabel;
        private Label trackSpeedLabel;
        private Label trackAltitudeLabel;
        private VisualElement confidenceFill;

        private ThreatTrack subject;

        private void OnEnable()
        {
            var document = GetComponent<UIDocument>();
            var rootDocument = document.rootVisualElement;
            if (rootDocument == null)
            {
                enabled = false;
                return;
            }

            root = rootDocument.Q<VisualElement>("root");
            trackIdLabel = rootDocument.Q<Label>("track-id");
            trackClassLabel = rootDocument.Q<Label>("track-class");
            trackSpeedLabel = rootDocument.Q<Label>("track-speed");
            trackAltitudeLabel = rootDocument.Q<Label>("track-altitude");
            confidenceFill = rootDocument.Q<VisualElement>("confidence-fill");

            if (root != null) root.style.display = DisplayStyle.None;

            EventBus.Subscribe<TrackSelected>(OnTrackSelected);
            EventBus.Subscribe<TrackDeselected>(OnTrackDeselected);
            EventBus.Subscribe<TrackUpdated>(OnTrackUpdated);
            EventBus.Subscribe<TrackStateChanged>(OnTrackStateChanged);
        }

        private void OnDisable()
        {
            EventBus.Unsubscribe<TrackSelected>(OnTrackSelected);
            EventBus.Unsubscribe<TrackDeselected>(OnTrackDeselected);
            EventBus.Unsubscribe<TrackUpdated>(OnTrackUpdated);
            EventBus.Unsubscribe<TrackStateChanged>(OnTrackStateChanged);
        }

        private void OnTrackSelected(TrackSelected evt)
        {
            subject = evt.Track;
            if (root != null) root.style.display = DisplayStyle.Flex;
            if (trackIdLabel != null) trackIdLabel.text = subject.Id;
            if (trackClassLabel != null) trackClassLabel.text = ClassLabel(subject.Archetype.ClassKind);
            RefreshKinematics(subject.LatestSample);
        }

        private void OnTrackDeselected(TrackDeselected evt)
        {
            if (subject != evt.Track) return;
            subject = null;
            if (root != null) root.style.display = DisplayStyle.None;
        }

        private void OnTrackUpdated(TrackUpdated evt)
        {
            if (subject != evt.Track) return;
            RefreshKinematics(evt.Sample);
        }

        private void OnTrackStateChanged(TrackStateChanged evt)
        {
            if (subject != evt.Track) return;
        }

        private void RefreshKinematics(KinematicSample sample)
        {
            if (trackSpeedLabel != null) trackSpeedLabel.text = $"M {sample.MachNumber:F1}";
            if (trackAltitudeLabel != null) trackAltitudeLabel.text = $"{sample.AltitudeMeters / 1000f:F0} KM";
            if (confidenceFill != null) confidenceFill.style.width = Length.Percent(sample.Confidence * 100f);
        }

        private static string ClassLabel(ThreatClass kind) => kind switch
        {
            ThreatClass.HypersonicGlideVehicle => "HGV",
            ThreatClass.ManeuveringReentryVehicle => "MARV",
            ThreatClass.BallisticReentryVehicle => "RV",
            ThreatClass.CruiseMissile => "CM",
            ThreatClass.UnmannedAerialSystem => "UAS",
            ThreatClass.Decoy => "DECOY",
            ThreatClass.Debris => "DEBRIS",
            _ => "UNK",
        };
    }
}
