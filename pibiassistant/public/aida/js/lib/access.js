import { __ } from "./i18n.js";

export const hasAccess = (win) => win.can_use !== false;

export const noAccessMessage = () =>
  __("You do not have access to AIDA. Ask an administrator for the PA User role.");
