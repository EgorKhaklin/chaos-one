using System.Collections;
using ChaosOne.Core;
using ChaosOne.Decisions;
using UnityEngine;

namespace ChaosOne.Scenarios
{
    /// <summary>
    /// Standalone scripted driver that pumps the Mode HUD and Decisions Panel
    /// in the absence of a live backend. Sequence:
    ///   T+ 4s   Transition Mode A -> B (sensor degraded)
    ///   T+ 8s   Propose three COAs (COA-B is recommended)
    ///   T+25s   Authorize COA-B from script (if operator hasn't already)
    ///   T+35s   Restore Mode B -> A
    ///   T+50s   Loop back to start
    /// </summary>
    public sealed class DemoEventDriver : MonoBehaviour
    {
        [SerializeField] private bool loop = true;
        [SerializeField] private float pauseBetweenLoopsSeconds = 8f;
        [SerializeField] private ModeStateMachine modeStateMachine;
        [SerializeField] private COAQueue coaQueue;

        private void Start()
        {
            StartCoroutine(Run());
        }

        private IEnumerator Run()
        {
            while (true)
            {
                yield return new WaitForSeconds(4f);
                if (modeStateMachine != null)
                {
                    modeStateMachine.Transition(OperationalMode.SensorDegraded);
                }

                yield return new WaitForSeconds(4f);

                if (coaQueue != null)
                {
                    coaQueue.Propose(BuildCoaB());
                    coaQueue.Propose(BuildCoaA());
                    coaQueue.Propose(BuildCoaC());
                }

                yield return new WaitForSeconds(17f);

                if (coaQueue != null)
                {
                    coaQueue.Authorize("COA-B", AuthorizationSource.AutoAuthorizedByROE);
                }

                yield return new WaitForSeconds(10f);

                if (modeStateMachine != null)
                {
                    modeStateMachine.Transition(OperationalMode.Nominal);
                }

                if (!loop) yield break;
                yield return new WaitForSeconds(pauseBetweenLoopsSeconds);

                if (coaQueue != null) coaQueue.ClearAll();
            }
        }

        private static CourseOfAction BuildCoaA() => new(
            id: "COA-A",
            headline: "Pure kinetic engagement",
            whyOneLine: "4× NGI on confirmed HGV midcourse. No directed-energy or non-kinetic.",
            expectedLeakage: new OutcomeBand(0.07f, 0.03f, 0.11f),
            cost: new MagazineDelta(ngi: 4),
            escalation: EscalationLevel.Moderate,
            releasability: "NATO",
            countdownSeconds: 10f,
            isRecommended: false);

        private static CourseOfAction BuildCoaB() => new(
            id: "COA-B",
            headline: "Mixed engagement",
            whyOneLine:
                "2× NGI on highest-confidence HGV. HEL warmed for swarm screen. Cyber deny adversary GNSS guidance under ROE-2.",
            expectedLeakage: new OutcomeBand(0.05f, 0.02f, 0.08f),
            cost: new MagazineDelta(ngi: 2, helMegajoules: 1.2f),
            escalation: EscalationLevel.Low,
            releasability: "NATO",
            countdownSeconds: 8f,
            isRecommended: true);

        private static CourseOfAction BuildCoaC() => new(
            id: "COA-C",
            headline: "Conservative reserve",
            whyOneLine: "Engage two threats now. Reserve NGI for projected Wave-2 launch in next 5 min.",
            expectedLeakage: new OutcomeBand(0.11f, 0.06f, 0.17f),
            cost: new MagazineDelta(ngi: 2),
            escalation: EscalationLevel.Low,
            releasability: "NATO",
            countdownSeconds: 12f,
            isRecommended: false);
    }
}
