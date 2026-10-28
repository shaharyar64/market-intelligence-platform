"use client";

import { useEffect, useState } from "react";
import DashboardTopbar from "@/components/layout/DashboardTopbar";

export default function HorecaAskAssistant() {
    return(
        <div className="min-h-screen bg-transparent">
            <DashboardTopbar
            title="Horeca Spatial Intelligence"
            />
            <div className="p-8">
                {/* comming soon content */}
                <h1 className="text-4xl font-bold text-center mt-20 text-gray-800">Ask Analytics Platform</h1>
                <p className="text-center mt-4 text-gray-600">Coming Soon...</p>
            </div>
        </div>
    );
}