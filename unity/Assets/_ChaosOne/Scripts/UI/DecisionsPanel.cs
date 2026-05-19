using System.Collections.Generic;
using ChaosOne.Core;
using ChaosOne.Decisions;
using UnityEngine;
using UnityEngine.UIElements;

namespace ChaosOne.UI
{
    /// <summary>
    /// Renders the active COA stack. Up to three cards visible at once, with
    /// the recommended COA visually privileged. Cards subscribe to countdown
    /// events and route Authorize / Object clicks back to the COAQueue.
    /// </summary>
    [RequireComponent(typeof(UIDocument))]
    public sealed class DecisionsPanel : MonoBehaviour
    {
        [SerializeField] private VisualTreeAsset coaCardTemplate;

        private VisualElement cardStack;
        private readonly Dictionary<string, COACardController> controllers = new();

        private void OnEnable()
        {
            var document = GetComponent<UIDocument>();
            UIDocumentLayout.FillPanel(document);
            var rv = document.rootVisualElement;
            if (rv == null) { enabled = false; return; }

            cardStack = rv.Q<VisualElement>("card-stack");

            EventBus.Subscribe<COAProposed>(OnCoaProposed);
            EventBus.Subscribe<COACountdownTick>(OnCountdownTick);
            EventBus.Subscribe<COAAuthorized>(OnAuthorized);
            EventBus.Subscribe<COAObjected>(OnObjected);
            EventBus.Subscribe<COAExpired>(OnExpired);
        }

        private void OnDisable()
        {
            EventBus.Unsubscribe<COAProposed>(OnCoaProposed);
            EventBus.Unsubscribe<COACountdownTick>(OnCountdownTick);
            EventBus.Unsubscribe<COAAuthorized>(OnAuthorized);
            EventBus.Unsubscribe<COAObjected>(OnObjected);
            EventBus.Unsubscribe<COAExpired>(OnExpired);
        }

        private void OnCoaProposed(COAProposed evt)
        {
            if (coaCardTemplate == null || cardStack == null) return;
            if (controllers.ContainsKey(evt.Coa.Id)) return;

            var cardRoot = coaCardTemplate.CloneTree();
            cardRoot.AddToClassList("coa-card");
            var controller = new COACardController(cardRoot, evt.Coa);

            controller.Authorized += OnControllerAuthorized;
            controller.Objected += OnControllerObjected;

            if (evt.Coa.IsRecommended)
            {
                cardStack.Insert(0, cardRoot);
            }
            else
            {
                cardStack.Add(cardRoot);
            }

            controllers[evt.Coa.Id] = controller;
        }

        private void OnCountdownTick(COACountdownTick evt)
        {
            if (controllers.TryGetValue(evt.CoaId, out var controller))
            {
                controller.UpdateCountdown(evt.SecondsRemaining);
            }
        }

        private void OnAuthorized(COAAuthorized evt) => DismissCard(evt.Coa.Id, "coa-card--authorized");
        private void OnObjected(COAObjected evt) => DismissCard(evt.Coa.Id, "coa-card--objected");
        private void OnExpired(COAExpired evt) => DismissCard(evt.Coa.Id, "coa-card--expired");

        private void DismissCard(string coaId, string transitionClass)
        {
            if (!controllers.TryGetValue(coaId, out var controller)) return;
            controller.Root.AddToClassList(transitionClass);
            cardStack?.Remove(controller.Root);
            controllers.Remove(coaId);
        }

        private static void OnControllerAuthorized(string coaId)
        {
            if (ServiceRegistry.TryResolve<COAQueue>(out var queue))
            {
                queue.Authorize(coaId, AuthorizationSource.Operator);
            }
        }

        private static void OnControllerObjected(string coaId)
        {
            if (ServiceRegistry.TryResolve<COAQueue>(out var queue))
            {
                queue.Object(coaId, "operator dissent");
            }
        }
    }
}
