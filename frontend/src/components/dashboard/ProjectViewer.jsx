import { useEffect, useMemo, useState } from "react";
import toast from "react-hot-toast";
import {
  Check,
  Clipboard,
  FileCode2,
  Folder,
  FolderOpen,
  Terminal,
} from "lucide-react";

import { getProjectFiles } from "../../api/api";

function formatBytes(bytes) {
  if (!Number.isFinite(bytes) || bytes < 1) {
    return "0 B";
  }

  if (bytes < 1024) {
    return `${bytes} B`;
  }

  if (bytes < 1024 * 1024) {
    return `${(bytes / 1024).toFixed(1)} KB`;
  }

  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function getFileName(filePath) {
  return filePath.split("/").pop() || filePath;
}

function FileIcon({ filePath }) {
  const fileName = getFileName(filePath).toLowerCase();

  if (
    fileName === "src" ||
    fileName === "app" ||
    fileName === "components"
  ) {
    return <Folder size={14} />;
  }

  return <FileCode2 size={14} />;
}

function buildFileTree(files) {
  const root = {
    type: "folder",
    name: "",
    children: [],
  };

  files.forEach((file) => {
    const parts = file.path.split("/");
    let current = root;

    parts.forEach((part, index) => {
      const isFile = index === parts.length - 1;

      if (isFile) {
        current.children.push({
          type: "file",
          name: part,
          path: file.path,
          file,
        });

        return;
      }

      let folder = current.children.find(
        (child) =>
          child.type === "folder" &&
          child.name === part,
      );

      if (!folder) {
        folder = {
          type: "folder",
          name: part,
          children: [],
        };

        current.children.push(folder);
      }

      current = folder;
    });
  });

  return root;
}

function sortTree(children) {
  return [...children].sort((a, b) => {
    if (a.type !== b.type) {
      return a.type === "folder" ? -1 : 1;
    }

    return a.name.localeCompare(b.name);
  });
}

function TreeNode({
  node,
  depth = 0,
  selectedPath,
  onSelect,
}) {
  const [open, setOpen] = useState(true);

  if (node.type === "file") {
    const selected = selectedPath === node.path;

    return (
      <button
        type="button"
        className={`aio-tree-file ${
          selected ? "is-selected" : ""
        }`}
        style={{
          paddingLeft: `${12 + depth * 16}px`,
        }}
        onClick={() => onSelect(node.file)}
      >
        <FileIcon filePath={node.path} />
        <span>{node.name}</span>
      </button>
    );
  }

  return (
    <div className="aio-tree-folder">
      {node.name && (
        <button
          type="button"
          className="aio-tree-folder-button"
          style={{
            paddingLeft: `${12 + depth * 16}px`,
          }}
          onClick={() => setOpen((value) => !value)}
        >
          {open ? (
            <FolderOpen size={14} />
          ) : (
            <Folder size={14} />
          )}

          <span>{node.name}</span>
        </button>
      )}

      {open &&
        sortTree(node.children).map((child) => (
          <TreeNode
            key={
              child.type === "file"
                ? child.path
                : `${node.name}/${child.name}`
            }
            node={child}
            depth={node.name ? depth + 1 : depth}
            selectedPath={selectedPath}
            onSelect={onSelect}
          />
        ))}
    </div>
  );
}

export default function ProjectViewer({
  projectName,
  execution,
  tests,
}) {
  const [files, setFiles] = useState([]);
  const [selectedFile, setSelectedFile] = useState(null);
  const [loading, setLoading] = useState(true);
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    let cancelled = false;

    const loadFiles = async () => {
      if (!projectName) {
        setLoading(false);
        return;
      }

      setLoading(true);

      try {
        const response = await getProjectFiles(projectName);

        if (cancelled) {
          return;
        }

        const nextFiles = Array.isArray(response?.files)
          ? response.files
          : [];

        setFiles(nextFiles);

        const firstReadableFile =
          nextFiles.find(
            (file) =>
              file.readable &&
              file.content !== null,
          ) || nextFiles[0];

        setSelectedFile(
          firstReadableFile || null,
        );
      } catch (error) {
        if (!cancelled) {
          console.error(
            "Failed to load project files:",
            error,
          );

          toast.error(
            error?.response?.data?.detail ||
              "Unable to load generated project files.",
          );
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    };

    loadFiles();

    return () => {
      cancelled = true;
    };
  }, [projectName]);

  const tree = useMemo(
    () => buildFileTree(files),
    [files],
  );

  const output = useMemo(() => {
    const executionOutput = [
      execution?.stdout,
      execution?.stderr,
    ]
      .filter(Boolean)
      .join("\n");

    const testOutput = [
      tests?.stdout,
      tests?.stderr,
    ]
      .filter(Boolean)
      .join("\n");

    if (!executionOutput && !testOutput) {
      return "";
    }

    const sections = [];

    if (executionOutput) {
      sections.push(
        "=== EXECUTION ===\n\n" +
          executionOutput,
      );
    }

    if (testOutput) {
      sections.push(
        "=== TESTS ===\n\n" +
          testOutput,
      );
    }

    return sections.join("\n\n");
  }, [execution, tests]);

  const copyCode = async () => {
    if (
      !selectedFile?.readable ||
      selectedFile.content === null
    ) {
      return;
    }

    try {
      await navigator.clipboard.writeText(
        selectedFile.content,
      );

      setCopied(true);

      window.setTimeout(() => {
        setCopied(false);
      }, 1600);

      toast.success("Code copied.");
    } catch (error) {
      console.error(
        "Failed to copy code:",
        error,
      );

      toast.error("Unable to copy code.");
    }
  };

  return (
    <section className="aio-project-viewer">
      <div className="aio-viewer-header">
        <div>
          <span className="aio-section-label">
            GENERATED SOURCE
          </span>

          <h2>Project files</h2>
        </div>

        <div className="aio-viewer-file-count">
          {files.length}{" "}
          {files.length === 1 ? "file" : "files"}
        </div>
      </div>

      {loading ? (
        <div className="aio-viewer-loading">
          Loading generated files...
        </div>
      ) : files.length === 0 ? (
        <div className="aio-viewer-empty">
          No generated files are available.
        </div>
      ) : (
        <div className="aio-viewer">
          <aside className="aio-file-tree">
            <div className="aio-file-tree-title">
              FILES
            </div>

            <div className="aio-file-tree-content">
              <TreeNode
                node={tree}
                selectedPath={selectedFile?.path}
                onSelect={setSelectedFile}
              />
            </div>
          </aside>

          <div className="aio-code-panel">
            <div className="aio-code-header">
              <div className="aio-code-file">
                <FileCode2 size={14} />

                <span>
                  {selectedFile?.path ||
                    "Select a file"}
                </span>
              </div>

              <button
                type="button"
                className="aio-copy-button"
                onClick={copyCode}
                disabled={
                  !selectedFile?.readable ||
                  selectedFile.content === null
                }
              >
                {copied ? (
                  <Check size={14} />
                ) : (
                  <Clipboard size={14} />
                )}

                {copied ? "Copied" : "Copy"}
              </button>
            </div>

            <div className="aio-code-content">
              {selectedFile?.readable &&
              selectedFile.content !== null ? (
                <pre>
                  <code>
                    {selectedFile.content}
                  </code>
                </pre>
              ) : selectedFile ? (
                <div className="aio-unreadable-file">
                  <FileCode2 size={20} />

                  <strong>
                    This file cannot be displayed.
                  </strong>

                  <span>
                    {selectedFile.reason ||
                      "The file is not readable as text."}
                  </span>

                  <small>
                    {formatBytes(
                      selectedFile.size,
                    )}
                  </small>
                </div>
              ) : (
                <div className="aio-unreadable-file">
                  Select a file from the project tree.
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {output && (
        <div className="aio-output-panel">
          <div className="aio-output-header">
            <div>
              <Terminal size={14} />
              <span>Run Output</span>
            </div>
          </div>

          <pre>{output}</pre>
        </div>
      )}
    </section>
  );
}