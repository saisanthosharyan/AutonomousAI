import {
  CheckCircle2,
  Circle,
  Loader2,
  XCircle,
} from "lucide-react";

const STEPS = [
  {
    key: "Planning",
    title: "Planning",
    percent: 10,
  },
  {
    key: "Coding",
    title: "Generating Code",
    percent: 30,
  },
  {
    key: "Building",
    title: "Building Project",
    percent: 50,
  },
  {
    key: "Executing",
    title: "Executing Project",
    percent: 65,
  },
  {
    key: "Debugging",
    title: "Debugging",
    percent: 70,
  },
  {
    key: "Retrying",
    title: "Self-Healing / Retry",
    percent: 75,
  },
  {
    key: "Validation",
    title: "Validating Project",
    percent: 80,
  },
  {
    key: "Testing",
    title: "Running Tests",
    percent: 85,
  },
  {
    key: "Review",
    title: "AI Review",
    percent: 90,
  },
  {
    key: "Evaluation",
    title: "Final Evaluation",
    percent: 95,
  },
  {
    key: "Completed",
    title: "Completed",
    percent: 100,
  },
];

export default function Progress({ runState }) {
  const progress = runState?.progress ?? 0;
  const currentStep = runState?.step ?? "";
  const status = runState?.status ?? "queued";

  const failed = status === "failed";

  return (
    <div className="rounded-2xl border border-gray-800 bg-gray-900 p-8 shadow-xl">
      <div className="mb-8 flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold">
            Live Pipeline
          </h2>

          <p className="mt-1 text-sm text-gray-400">
            Autonomous software engineering process
          </p>
        </div>

        <div className="text-right">
          <div className="text-3xl font-bold text-cyan-400">
            {progress}%
          </div>

          <div className="text-xs uppercase text-gray-500">
            {status}
          </div>
        </div>
      </div>

      <div className="mb-8 h-3 overflow-hidden rounded-full bg-gray-800">
        <div
          className="h-full rounded-full bg-gradient-to-r from-cyan-400 to-blue-500 transition-all duration-700"
          style={{
            width: `${Math.min(progress, 100)}%`,
          }}
        />
      </div>

      <div className="space-y-5">
        {STEPS.map((step) => {
          const completed =
            progress >= step.percent;

          const active =
            currentStep
              ?.toLowerCase()
              .includes(step.key.toLowerCase());

          const isFailed =
            failed && active;

          return (
            <div
              key={step.key}
              className="flex items-center gap-4"
            >
              <div className="shrink-0">
                {isFailed ? (
                  <XCircle
                    size={22}
                    className="text-red-400"
                  />
                ) : completed ? (
                  <CheckCircle2
                    size={22}
                    className="text-green-400"
                  />
                ) : active ? (
                  <Loader2
                    size={22}
                    className="animate-spin text-cyan-400"
                  />
                ) : (
                  <Circle
                    size={22}
                    className="text-gray-600"
                  />
                )}
              </div>

              <div className="flex-1">
                <div className="flex items-center justify-between">
                  <span
                    className={
                      active
                        ? "font-semibold text-white"
                        : "text-gray-400"
                    }
                  >
                    {step.title}
                  </span>

                  <span className="text-sm text-gray-500">
                    {step.percent}%
                  </span>
                </div>
              </div>
            </div>
          );
        })}
      </div>

      <div className="mt-8 rounded-xl border border-gray-800 bg-gray-950 p-4">
        <p className="text-sm text-gray-400">
          Current activity
        </p>

        <p
          className={`mt-1 ${
            failed
              ? "text-red-400"
              : "text-white"
          }`}
        >
          {runState?.message ||
            "Waiting for a project generation request..."}
        </p>

        {runState?.error && (
          <p className="mt-2 text-sm text-red-400">
            {runState.error}
          </p>
        )}
      </div>
    </div>
  );
}