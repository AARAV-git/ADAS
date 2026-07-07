import { NextResponse } from "next/server";
import { generateAlert } from "@/lib/mock-data";

export async function GET() {
  const alerts = Array.from({ length: 10 }, () => generateAlert());
  return NextResponse.json(alerts);
}
