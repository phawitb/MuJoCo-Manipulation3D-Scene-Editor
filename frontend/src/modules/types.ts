import type { ComponentType } from "react";
export type RobotControlProps = { sessionId: string | null };
export type ModuleProps = {
  activeTab?: boolean;
  robotControls?: ComponentType<RobotControlProps>;
};
