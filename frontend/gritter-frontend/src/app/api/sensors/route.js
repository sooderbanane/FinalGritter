import { NextResponse } from 'next/server';
import fs from 'fs';
import path from 'path';

export async function GET() {

    const dir = path.join(process.cwd(), 'public/sensor_data');  // or 'sensor_data' or 'public/sensor_data'
    const files = fs.readdirSync(dir).filter(file => file.endsWith('.csv'));
    return NextResponse.json(files);
}