import { Suspense } from "react";
import LoginLayout from "@/components/auth/LoginLayout";
import LoginForm from "@/components/auth/LoginForm";

export default function LoginPage() {
  return (
    <LoginLayout>
      <Suspense>
        <LoginForm />
      </Suspense>
    </LoginLayout>
  );
}
