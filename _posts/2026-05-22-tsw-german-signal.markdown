---
layout: post
title:  "Learning note for german rail signal"
date:   2026-05-22 22:01:00 0100
categories: [game]
---



## Fundamental

Two signal systems
- PZB
- LZB

## Light signal

Two types of signals
- main signal
- distance signal

### Main signal

**Green**
Clear to proceed at current line speed

**Green over yellow**
Proceed at 40 km/h

**Red**
Stop at this signal

**White number on top of signal**
Indicate speed of proceeding

**Blinking green**
Proceed at line speed, expect to slow down at next signal.

### Distance signal
Indicate the main signal ahead. Lights are at diagonal angle. White light indicate this distance signal is closer to main signal than usual.

**Double green**

Next main signal is clear

**Green over yellow**
Proceed at 40 km/h

**Two yellow lights**
Expect to stop at next main signal

### Shunt signal

**Two horizontal red light**
Not clear to proceed

**Two diagonal white light**
Clear to proceed at 40 km/h

## PZB

There are three modes for PZB. The number for each mode indicate the speed to reduce to when passing cautionary signal (diagonal yellow).

- O mode for passenger train, illuminate 85.

### PZB control

**PZB acknowledge**

Pgdown

**PZB release**

end

**PZB overide**

del

### SOP

#### Passing cautionary signal

1. Press acknowledge when pass cautionary signal
2. 1000hz magnet light up
3. reduce speed to below 85 km/h
4. When 1000Hz magnet light off. If the path is clear ahead, press PZB release and accelerate. If not clear, decrease speed to 65 km/h.
5. When 500Hz magnet light up, decelerate to 45 km/h. 
6. Stop before red signal
7. If get permission from the signaler, press and hold the overide button and move forward.
8. Keep speed below 40 km/h after passing this way untile travel 2km or pass a clear signal. After which press pzb release and accelerate. 

**note**
- No need for acknowledge of 500Hz magnet
- Can't go over 45 km/h after passing 500Hz even if signal is clear. The restriction last for 250m pass the signal. 


## LZB

Indicate by the U light.

When AFB active, the speed automatically adjust.

B lamp indicate whether auto braking is active. 
G lamp indicate it is faster than the braking curve allows.

When reaching end of LZB section

1.  ende light up
2.  press PZB acknowledge

## Signs


**Speed Post**

![Speed Post](https://img.xiyivan.com/2026/06/speed-post.png)

Show speed limit divide by ten. Arrow above the post indicates the track this speed limit applies to.


**Speed Limit Warning Post**

![Speed List Warning Post](https://img.xiyivan.com/2026/06/speed-limit-warning-post.png)

Indicate the upcoming speed change. May contain pzb magnet.


**Distance Marker Post**

![Distance marker post](https://img.xiyivan.com/2026/06/distance-marker-post.png)

Represent distance to an upcoming signal. 3 stripes — 250m; 2 stripes — 175m; 1 stripe — 100m.


**Hectometer Post**

![Hectometer post](https://img.xiyivan.com/2026/06/hectometer-post.png)

Exist every 200m. Indicate location from a location.


**P Sign**

![P sign](https://img.xiyivan.com/2026/06/p-sign.png)

Sound horn when passing P sign.


**H Sign**

![H sign](https://img.xiyivan.com/2026/06/h-sign.png)

Indicate stopping location.





Credit to [PTGRail](https://www.youtube.com/@PTGRail) for the amazing video he made about this topic.
