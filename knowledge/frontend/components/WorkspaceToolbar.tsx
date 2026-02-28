import { useTheme } from "@mui/material/styles";
import { Box, Toolbar, ButtonBase, Tooltip, IconButton } from "@mui/material";
import { Chat } from "@carbon/icons-react";
import {
  useWorkspace,
  type WorkspaceState,
} from "../contexts/WorkspaceContext";

const stateItems: { key: WorkspaceState; label: string }[] = [
  // { key: 'draft', label: 'Draft' },
  { key: "setup", label: "Setup" },
  { key: "working", label: "Working" },
  { key: "action", label: "Action" },
];

export default function WorkspaceToolbar() {
  const theme = useTheme();
  const { chatOpen, setChatOpen, workspaceState, setWorkspaceState } =
    useWorkspace();

  const activeIndex = stateItems.findIndex(
    (item) => item.key === workspaceState
  );

  const handleChange = (next: WorkspaceState) => {
    setWorkspaceState(next);
  };

  return (
    <Box
      component="header"
      sx={{
        position: "sticky",
        top: 0,
        px: 2,
        mr: { xs: 0, sm: chatOpen ? "360px" : 0, md: chatOpen ? "420px" : 0 },
        transition: theme.transitions.create("margin", {
          easing: theme.transitions.easing.sharp,
          duration: theme.transitions.duration.leavingScreen,
        }),
        zIndex: (t) => t.zIndex.appBar,
        bgcolor: "background.default",
        borderBottom: "1px solid",
        borderColor: "divider",
      }}
    >
      <Toolbar
        disableGutters
        sx={{
          minHeight: 50,
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          "@media (min-width:600px)": {
            minHeight: 50, // override the default 64px
          },
        }}
      >
        <Box sx={{ display: "flex", alignItems: "center" }}>
          {stateItems.map((item, index) => {
            const active = workspaceState === item.key;

            return (
              <Box
                key={item.key}
                sx={{ display: "flex", alignItems: "center" }}
              >
                {/* Icon + label */}
                <ButtonBase
                  onClick={() => handleChange(item.key)}
                  sx={{
                    display: "flex",
                    alignItems: "center",
                    gap: 1,
                  }}
                >
                  {/* Outer square */}
                  <Box
                    sx={{
                      width: 22,
                      height: 22,
                      borderRadius: 0.5,
                      border: "1px solid",
                      borderColor: active
                        ? theme.palette.primary.main
                        : theme.palette.grey[300],
                      bgcolor: active
                        ? theme.palette.primary.main
                        : "transparent",
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "center",
                    }}
                  >
                    {/* Inner square */}
                    <Box
                      sx={{
                        width: 10,
                        height: 10,
                        borderRadius: 0.2,
                        bgcolor: active
                          ? theme.palette.common.white
                          : theme.palette.grey[200],
                      }}
                    />
                  </Box>

                  {/* Label */}
                  <Box
                    component="span"
                    sx={{
                      fontWeight: active ? 600 : 400,
                      fontSize: 14,
                      color: "text.primary",
                    }}
                  >
                    {item.label}
                  </Box>
                </ButtonBase>

                {/* Connector line (between items) */}
                {index < stateItems.length - 1 && (
                  <Box
                    sx={{
                      width: 40,
                      height: 1.5,
                      mx: 1,
                      bgcolor:
                        activeIndex > index
                          ? theme.palette.primary.main // “progress” up to the active state
                          : theme.palette.grey[300],
                    }}
                  />
                )}
              </Box>
            );
          })}
        </Box>
        <Box sx={{ display: "flex", alignItems: "center", gap: 1 }}>
          {!chatOpen && (
            <Tooltip title="Open chat">
              <IconButton
                onClick={() => setChatOpen(true)}
                sx={{ color: "secondary.main" }}
              >
                <Chat size={24} />
              </IconButton>
            </Tooltip>
          )}
        </Box>
      </Toolbar>
    </Box>
  );
}
