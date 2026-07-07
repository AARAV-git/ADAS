import { NextResponse } from "next/server";
import { generateStatsOverview } from "@/lib/mock-data";

export async function GET() {
  const stats = generateStatsOverview();
  return NextResponse.json(stats);
}
