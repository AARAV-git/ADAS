import { NextResponse } from "next/server";
import { generateExplainResponse } from "@/lib/mock-data";

export async function POST(request: Request) {
  // Parse the request body (for future real API integration)
  await request.json();

  // Simulate AI processing delay
  await new Promise((resolve) => setTimeout(resolve, 500));

  const explanation = generateExplainResponse();
  return NextResponse.json(explanation);
}
