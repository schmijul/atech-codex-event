#pragma once
#include <Arduino.h>
#include <Adafruit_ST7735.h>

// All candidates use only the four port-derived display signal pins.
// The display's CS, DC, MOSI and SCLK are all inputs.
class DisplayProbe {
  int pins[4];
public:
  DisplayProbe(int a, int b, int c, int d) : pins{a,b,c,d} {}
  void probe(int wanted) {
    int index = 0;
    for (int clk=0; clk<4; ++clk)
      for (int cs=0; cs<4; ++cs) {
        if (cs==clk) continue;
        for (int mosi=0; mosi<4; ++mosi) {
          if (mosi==clk || mosi==cs) continue;
          int dc=6-clk-cs-mosi;
          if (index++ != wanted) continue;
          Serial.printf("PROBE %d: CLK=%d CS=%d MOSI=%d DC=%d\n",
                        wanted+1,pins[clk],pins[cs],pins[mosi],pins[dc]);
          Adafruit_ST7735 panel(pins[cs],pins[dc],pins[mosi],pins[clk],-1);
          panel.initR(INITR_MINI160x80);
          panel.setSPISpeed(1000000);
          panel.setRotation(3);
          panel.invertDisplay(false);
          panel.fillScreen(ST77XX_BLUE);
          panel.setTextColor(ST77XX_WHITE);
          panel.setTextSize(2);
          panel.setCursor(12,10);
          panel.print("TEST "); panel.print(wanted+1);
          panel.setCursor(12,36);
          panel.print("Codex!");
          return;
        }
      }
  }
};
