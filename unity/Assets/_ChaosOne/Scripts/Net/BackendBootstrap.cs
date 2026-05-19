using System.Threading;
using ChaosOne.Core;
using UnityEngine;

namespace ChaosOne.Net
{
    public enum BackendMode
    {
        Scripted,
        Grpc,
    }

    /// <summary>
    /// Scene-resident bootstrap. Constructs the chosen backend client, starts
    /// it, registers it in the ServiceRegistry, and cleans up on shutdown.
    /// </summary>
    public sealed class BackendBootstrap : MonoBehaviour
    {
        [SerializeField] private BackendMode mode = BackendMode.Scripted;
        [SerializeField] private string grpcAddress = "http://127.0.0.1:50051";

        private IChaosBackendClient client;
        private ScriptedFeed scriptedFeed;
        private CancellationTokenSource lifetimeCts;

        private async void Start()
        {
            client = mode switch
            {
                BackendMode.Scripted => new ScriptedChaosBackendClient(),
                BackendMode.Grpc => new GrpcChaosBackendClient(grpcAddress),
                _ => new ScriptedChaosBackendClient(),
            };

            lifetimeCts = new CancellationTokenSource();
            await client.StartAsync(lifetimeCts.Token);

            ServiceRegistry.Register(client);
            if (client is ICourseOfActionGenerator generator)
            {
                ServiceRegistry.Register(generator);
            }

            if (mode == BackendMode.Scripted)
            {
                scriptedFeed = gameObject.AddComponent<ScriptedFeed>();
            }
        }

        private async void OnDestroy()
        {
            lifetimeCts?.Cancel();
            if (client != null)
            {
                await client.StopAsync();
            }
            if (scriptedFeed != null)
            {
                Destroy(scriptedFeed);
                scriptedFeed = null;
            }
            ServiceRegistry.Unregister<IChaosBackendClient>();
            ServiceRegistry.Unregister<ICourseOfActionGenerator>();
            lifetimeCts?.Dispose();
            lifetimeCts = null;
        }
    }
}
