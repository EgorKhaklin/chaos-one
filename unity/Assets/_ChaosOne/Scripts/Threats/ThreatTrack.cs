using System;
using ChaosOne.Core;
using UnityEngine;

namespace ChaosOne.Threats
{
    [DisallowMultipleComponent]
    public sealed class ThreatTrack : MonoBehaviour
    {
        [SerializeField] private ThreatArchetype archetype;
        [SerializeField] private string trackId;
        [SerializeField] private TrackState initialState = TrackState.Acquiring;

        private KinematicSample latestSample;
        private TrackState state;
        private bool spawned;

        public string Id => trackId;
        public ThreatArchetype Archetype => archetype;
        public TrackState State => state;
        public KinematicSample LatestSample => latestSample;

        public void Configure(ThreatArchetype assignedArchetype, string assignedId, TrackState assignedState)
        {
            archetype = assignedArchetype;
            trackId = assignedId;
            initialState = assignedState;
        }

        private void Awake()
        {
            if (string.IsNullOrEmpty(trackId))
            {
                trackId = "T-" + Guid.NewGuid().ToString("N").Substring(0, 6).ToUpperInvariant();
            }
            state = initialState;
        }

        private void OnEnable()
        {
            if (spawned) return;
            spawned = true;
            EventBus.Publish(new TrackSpawned(this));
        }

        private void OnDestroy()
        {
            if (!spawned) return;
            EventBus.Publish(new TrackDestroyed(this));
        }

        public void ApplySample(KinematicSample sample)
        {
            latestSample = sample;
            transform.SetPositionAndRotation(sample.Position, sample.Orientation);
            EventBus.Publish(new TrackUpdated(this, sample));
        }

        public void SetState(TrackState next)
        {
            if (state == next) return;
            var previous = state;
            state = next;
            EventBus.Publish(new TrackStateChanged(this, previous, next));
        }
    }
}
