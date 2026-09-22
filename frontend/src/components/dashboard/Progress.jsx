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
  },
  {
    key: "Coding",
    title: "Generating Code",
  },
  {
    key: "Building",
    title: "Building Project",
  },
  {
    key: "Execution",
    title: "Executing Project",
  },
  {
    key: "Testing",
    title: "Running Tests",
  },
  {
    key: "Review",
    title: "AI Review",
  },
  {
    key: "Validation",
    title: "Validating Project",
  },
  {
    key: "Evaluation",
    title: "Final Evaluation",
  },
  {
    key: "Saving",
    title: "Saving Project",
  },
  {
    key: "Completed",
    title: "Completed",
  },
];

export default function Progress({ runState }) {
  const progress = Math.min(runState?.progress ?? 0, 100);
  const currentStep = runState?.step ?? "";
  const status = runState?.status ?? "queued";

  const failed = status === "failed";

  const currentIndex = STEPS.findIndex(
    (step) =>
      currentStep.toLowerCase() === step.key.toLowerCase()
  );

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
            width: `${progress}%`,
          }}
        />
      </div>

      <div className="space-y-5">
        {STEPS.map((step, index) => {
          const isCurrent =
            index === currentIndex;

          const isCompleted =
            currentIndex > index ||
            (step.key === "Completed" &&
              status === "completed");

          const isFailed =
            failed && isCurrent;

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
                ) : isCompleted ? (
                  <CheckCircle2
                    size={22}
                    className="text-green-400"
                  />
                ) : isCurrent ? (
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
                      isCurrent
                        ? "font-semibold text-white"
                        : isCompleted
                          ? "text-gray-300"
                          : "text-gray-500"
                    }
                  >
                    {step.title}
                  </span>

                  {isCurrent && (
                    <span className="text-sm text-cyan-400">
                      {progress}%
                    </span>
                  )}
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