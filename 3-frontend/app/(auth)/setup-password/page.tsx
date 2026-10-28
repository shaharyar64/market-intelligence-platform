import { Suspense } from "react";
import LoginLayout from "@/components/auth/LoginLayout";
import PasswordSetupForm from "@/components/auth/PasswordSetupForm";

export default function SetupPasswordPage() {
  return (
    <LoginLayout>
      <Suspense>
        <PasswordSetupForm variant="setup" />
      </Suspense>
    </LoginLayout>
  );
}
