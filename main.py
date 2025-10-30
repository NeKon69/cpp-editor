import time
from src.lsp_server.session import LspSession
import sansio_lsp_client as lsp

if __name__ == "__main__":
    project_path = "/home/progamers/cpp_editor/lsp_test_project"
    with LspSession(project_path) as session:
        session.open_file("main.cpp")
        time.sleep(2)

        completions = session.get_completion("main.cpp", line=2, character=11)
        if completions:
            print(f"Found {len(completions.items)} completions")

        hover = session.get_hover("main.cpp", line=2, character=8)
        if hover:
            print(f"Hover: {hover}")

        change_range = lsp.Range(
            start=lsp.Position(line=2, character=0),
            end=lsp.Position(line=2, character=10),
        )
        session.on_incremental_change("main.cpp", change_range, "new code")

        diagnostics = session.get_diagnostics("main.cpp")
        print(f"Found {len(diagnostics)} diagnostics")

        session.close_file("main.cpp")
