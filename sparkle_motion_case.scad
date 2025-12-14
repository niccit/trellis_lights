// SPDX-License-Identifier: MIT
$fa = 1;
$fs = 0.4;

include <YAPP_Box/YAPPgenerator_v3.scad>

// Feather ESP32v2 case for Aluminum Tree Lights

printBaseShell = true;
printLidShell = true;

// 52.3mm x 22.8mm x 7.2mm per https://www.adafruit.com/product/5400
pcbLength = 50.8;
pcbWidth = 33.02;
pcbThickness = 1.6;

paddingLeft = 4;
paddingRight = 2;
paddingFront = 2;
paddingBack = 2;

wallThickness = 1.5;
basePlaneThickness = 1.5;
lidPlaneThickness = 1.5;

// 25 mm total height
baseWallHeight = 15;
lidWallHeight = 10;

ridgeHeight = 5;
ridgeSlack = 0.2;
roundRadius = 2.0;

standoffHeight = 5.0;
standoffPinDiameter = 2;
standoffHoleSlack = 0.5;
standoffDiameter = 4;

pcbStands = [
   [2, 1.25, yappHole, yappBaseOnly, yappSelfThreading]        // back left
   ,[2, 29, yappHole, yappBaseOnly, yappSelfThreading]         // back right
   ,[47.75, 1.25, yappHole, yappBaseOnly, yappSelfThreading]   // front left
   ,[47.75, 29, yappHole, yappBaseOnly, yappSelfThreading]     // front right
   ];

cutoutsBack = [
   [5, 1, 10, 11, 0, yappRectangle]
   ,[14, 1, 11, 3, 0, yappRectangle]
   ];

cutoutsFront = [
   [3, -2, 23, 9, 0, yappRectangle]
   ];

boxMounts =
   [
      [10, 5, shellWidth, 3, yappBack]
   ,[-10, 5, shellWidth, 3, yappFront]
   ];


YAPPgenerate();