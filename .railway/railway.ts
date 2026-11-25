import { defineRailway, github, project, service, volume } from "railway/iac";
// This repository manages only its own resources in the environment. Other
// repositories export their own partial name.
// See https://docs.railway.com/infrastructure-as-code#multi-repo-projects
export const partial = "Tushum-AI-";
export default defineRailway(() => {
  const data = volume("tushum-data", { sizeMB: 500, region: "sfo" });
  const TushumAI = service("Tushum-AI-", {
    source: github("elyornishonboyev25-alt/Tushum-AI-", { branch: "main", checkSuites: false, rootDirectory: "/" }),
    build: { buildEnvironment: "V3", builder: "DOCKERFILE", dockerfilePath: "Dockerfile" },
    volumeMounts: { "/data": data },
    healthcheck: "/api/health",
    healthcheckTimeout: 120,
    replicas: { "sfo": 1 },
    deploy: { drainingSeconds: 15, overlapSeconds: 0, restartPolicyMaxRetries: 3 },
    networking: { privateNetworkEndpoint: "tushum-ai", serviceDomains: { "tushum-ai-production-fe6eb70d.up.railway.app": { port: 8080 } } },
  });

  return project("striking-youth", {
    variables: { managed: false },
    resources: [data, TushumAI],
  });
});
