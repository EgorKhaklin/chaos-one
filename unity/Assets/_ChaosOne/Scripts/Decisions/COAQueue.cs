using System.Collections.Generic;
using ChaosOne.Core;
using UnityEngine;

namespace ChaosOne.Decisions
{
    /// <summary>
    /// Tracks active COAs, ticks their countdowns, and resolves expiry under
    /// the active ROE envelope. Caps active set at three (Phase 2 §2.4.4
    /// cognitive-load cap: never more than three options on screen).
    /// </summary>
    public sealed class COAQueue : MonoBehaviour
    {
        [SerializeField] private ROEEnvelope envelope;
        [SerializeField] private int maxActive = 3;

        private readonly List<ActiveEntry> active = new();

        public ROEEnvelope ActiveEnvelope => envelope;

        public IReadOnlyList<CourseOfAction> ActiveCoas
        {
            get
            {
                var snapshot = new List<CourseOfAction>(active.Count);
                foreach (var entry in active) snapshot.Add(entry.Coa);
                return snapshot;
            }
        }

        private void Awake()
        {
            ServiceRegistry.Register(this);
        }

        private void OnDestroy()
        {
            ServiceRegistry.Unregister<COAQueue>();
        }

        private void Update()
        {
            if (active.Count == 0) return;

            for (var i = active.Count - 1; i >= 0; i--)
            {
                var entry = active[i];
                entry.Remaining -= Time.deltaTime;
                active[i] = entry;

                EventBus.Publish(new COACountdownTick(entry.Coa.Id, Mathf.Max(0f, entry.Remaining)));

                if (entry.Remaining <= 0f)
                {
                    ResolveExpiry(entry.Coa);
                    active.RemoveAt(i);
                }
            }
        }

        public void Propose(CourseOfAction coa)
        {
            if (coa == null) return;
            if (active.Count >= maxActive) return;
            if (Contains(coa.Id)) return;

            active.Add(new ActiveEntry { Coa = coa, Remaining = coa.CountdownSeconds });
            EventBus.Publish(new COAProposed(coa));
        }

        public bool Authorize(string coaId, AuthorizationSource source = AuthorizationSource.Operator)
        {
            for (var i = 0; i < active.Count; i++)
            {
                if (active[i].Coa.Id != coaId) continue;
                var coa = active[i].Coa;
                active.RemoveAt(i);
                EventBus.Publish(new COAAuthorized(coa, source));
                return true;
            }
            return false;
        }

        public bool Object(string coaId, string reason)
        {
            for (var i = 0; i < active.Count; i++)
            {
                if (active[i].Coa.Id != coaId) continue;
                var coa = active[i].Coa;
                active.RemoveAt(i);
                EventBus.Publish(new COAObjected(coa, reason));
                return true;
            }
            return false;
        }

        public void ClearAll()
        {
            for (var i = active.Count - 1; i >= 0; i--)
            {
                EventBus.Publish(new COAExpired(active[i].Coa));
            }
            active.Clear();
        }

        private void ResolveExpiry(CourseOfAction coa)
        {
            if (envelope != null && coa.IsRecommended && envelope.PermitsAutoAuthorize(coa))
            {
                EventBus.Publish(new COAAuthorized(coa, AuthorizationSource.AutoAuthorizedByROE));
            }
            else
            {
                EventBus.Publish(new COAExpired(coa));
            }
        }

        private bool Contains(string coaId)
        {
            foreach (var entry in active)
            {
                if (entry.Coa.Id == coaId) return true;
            }
            return false;
        }

        private struct ActiveEntry
        {
            public CourseOfAction Coa;
            public float Remaining;
        }
    }
}
