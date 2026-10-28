import { Suspense } from "react";
import LoginLayout from "@/components/auth/LoginLayout";
import PasswordSetupForm from "@/components/auth/PasswordSetupForm";

export default function ResetPasswordPage() {
  return (
    <LoginLayout>
      <Suspense>
        <PasswordSetupForm variant="reset" />
      </Suspense>
    </LoginLayout>
  );
}
