import { NextResponse } from "next/server";
import { generateSessions } from "@/lib/mock-data";

export async function GET() {
  const sessions = generateSessions();
  return NextResponse.json(sessions);
}
