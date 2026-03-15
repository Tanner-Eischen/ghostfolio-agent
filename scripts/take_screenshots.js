// Screenshot script using Puppeteer
// Run: node scripts/take_screenshots.js

const puppeteer = require('puppeteer');
const fs = require('fs');
const path = require('path');

const BASE_URL = process.env.DEMO_URL || 'https://ghostfolio-frontend-production.up.railway.app';
const OUTPUT_DIR = path.join(__dirname, '..', 'docs', 'screenshots');

async function takeScreenshots() {
  const browser = await puppeteer.launch({ headless: true });
  const page = await browser.newPage();

  // Set viewport for consistent screenshots
  await page.setViewport({ width: 1280, height: 800 });

  // Create output directory
  if (!fs.existsSync(OUTPUT_DIR)) {
    fs.mkdirSync(OUTPUT_DIR, { recursive: true });
  }

  console.log('Taking screenshots of', BASE_URL);

  // 1. Homepage with demo banner
  console.log('1. Capturing homepage...');
  await page.goto(BASE_URL, { waitUntil: 'networkidle0' });
  await page.waitForTimeout(2000);
  await page.screenshot({
    path: path.join(OUTPUT_DIR, 'homepage-demo-mode.png'),
    fullPage: false
  });

  // 2. Send a chat message
  console.log('2. Capturing chat interaction...');
  const input = await page.$('input[type="text"], textarea');
  if (input) {
    await input.type("What's my portfolio worth?");
    await page.keyboard.press('Enter');
    await page.waitForTimeout(5000); // Wait for response
    await page.screenshot({
      path: path.join(OUTPUT_DIR, 'chat-response.png'),
      fullPage: false
    });
  }

  // 3. Mobile view
  console.log('3. Capturing mobile view...');
  await page.setViewport({ width: 375, height: 812 });
  await page.goto(BASE_URL, { waitUntil: 'networkidle0' });
  await page.waitForTimeout(2000);
  await page.screenshot({
    path: path.join(OUTPUT_DIR, 'mobile-view.png'),
    fullPage: false
  });

  await browser.close();
  console.log('Screenshots saved to', OUTPUT_DIR);
}

takeScreenshots().catch(console.error);
