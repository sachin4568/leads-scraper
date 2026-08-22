"use client";

import { SettingsDrawer } from "./SettingsDrawer";

interface SettingsModalProps {
  isOpen: boolean;
  onClose: () => void;
  token: string;
}

export function SettingsModal({ isOpen, onClose, token }: SettingsModalProps) {
  return <SettingsDrawer isOpen={isOpen} onClose={onClose} token={token} />;
}
