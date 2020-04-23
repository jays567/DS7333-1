---
title: "Team CCAD Case Study 1: RTLS Analysis"
author: "David Josephs, Andy Heroy, Carson Drake, Che' Cobb"
date: "2020-01-21"
output: 
  html_document:
    toc: true
    number_sections: true
    theme: united
    highlight: haddock
    code_folding: hide
    df_print: paged
    keep_md: TRUE
    fig_width: 10
    fig_height: 10
    fig_retina: true
---



# Introduction

Businesses today often need to know where items of interest (such as people or machinery) are at any given point in time, within a specified area.
Tracking items indoors provides an interesting challenge as conventional methods (GPS) for establishing location don’t work well indoors.
Nolan and Lang propose an innovative solution to this problem by combining machine learning techniques (K-Nearest Neighbors), and wifi signals in order to create an indoor map that can locate and estimate where a given item of interest is by assessing its signal strength at various access points (wifi routers) placed throughout the area.  This information proves vital to optimizing workflows for how objects move throughout a space, and how improve upon their future handling to best accommodate the business’s needs.

The experimental setup is shown in detail in the figure below:


```r
knitr::include_graphics("CleverZonkedElk.png")
```

<div class="figure" style="text-align: center">
<img src="CleverZonkedElk.png" alt="**Floor plan of the test environment:** *Access Points Denoted by black squares. training data selected at grey dots, online test data selected at black dots. Gray dots are approximately one meter apart*"  />
<p class="caption">**Floor plan of the test environment:** *Access Points Denoted by black squares. training data selected at grey dots, online test data selected at black dots. Gray dots are approximately one meter apart*</p>
</div>

Researchers mapped the static signal strengths of the various access points throughout the space. These routers communicate with a scanning device, which was placed methodically at known intervals throughout the area. This collection makes up the offline (training) data, while later online training data was collected by more or less walking around with the sensor. The raw data is arranged by router, and described below:

## Data Description


```r
pander::pander(list(t = "Time stamp (Milliseconds) since 12:00am, January 1, 1970", 
    Id = "router MAC address", Pos = "Router location", Degree = "Direction scanning device was carried by the researcher, measured in Degrees", 
    MAC = "MAC address of either the accessrouter, or scanning device combined with corresponding values for signal strength (dBm), the mode in which it was operating(adhoc scanner = 1, access router = 3), and its corresponding channel frequency.", 
    Signal = "Received Signal Strength in DbM"))
```



  * **t**: Time stamp (Milliseconds) since 12:00am, January 1, 1970
  * **Id**: router MAC address
  * **Pos**: Router location
  * **Degree**: Direction scanning device was carried by the researcher, measured in Degrees
  * **MAC**: MAC address of either the accessrouter, or scanning device combined with corresponding values for signal strength (dBm), the mode in which it was operating(adhoc scanner = 1, access router = 3), and its corresponding channel frequency.
  * **Signal**: Received Signal Strength in DbM

<!-- end of list -->

## Data Formatting

The data is initially read in as raw text. Several measures were taken in order to get the data into a tabular format which an algorithm such as KNN can operate on. First, the raw text was split into tokens by separating markers. These tokens were then stripped of all comments and extraneous information. Then, to make the problem computationally simpler, the angles were rounded into discrete intervals of 45 degrees. Finally, the data was stripped of variables which were not pertinent to the analysis.


```r
knitr::read_chunk("utils.R")
knitr::read_chunk("analysis_plots.R")
knitr::read_chunk("excl_b.R")
```


```r
# first we define the processline function, which unsurprisingly processes a
# single line of the offline or online.txt
library(tidyverse)
processLine = function(x) {
    # here we split the line at the weird markers. Strsplit returns a list we
    # take the first item of the list
    tokens = strsplit(x, "[;=,]")[[1]]
    if (length(tokens) == 10) {
        return(NULL)
    }
    # now we are going to stack the tokens
    tmp = matrix(tokens[-(1:10)], , 4, byrow = TRUE)
    cbind(matrix(tokens[c(2, 4, 6:8, 10)], nrow(tmp), 6, byrow = TRUE), tmp)
}
roundOrientation = function(angles) {
    refs = seq(0, by = 45, length = 9)
    q = sapply(angles, function(o) which.min(abs(o - refs)))
    c(refs[1:8], 0)[q]
}
# this reads in the data
readData <- function(filename, subMacs = c("00:0f:a3:39:e1:c0", "00:0f:a3:39:dd:cd", 
    "00:14:bf:b1:97:8a", "00:14:bf:3b:c7:c6", "00:14:bf:b1:97:90", "00:14:bf:b1:97:8d", 
    "00:14:bf:b1:97:81")) {
    # read it in line by line
    txt = readLines(filename)
    # ignore comments
    lines = txt[substr(txt, 1, 1) != "#"]
    # process (tokenize and stack) each line
    tmp = lapply(lines, processLine)
    # rbind each elemnt of the list together
    offline = as.data.frame(do.call(rbind, tmp), stringsAsFactors = FALSE)
    # set the names of our matrix
    names(offline) = c("time", "scanMac", "posX", "posY", "posZ", "orientation", 
        "mac", "signal", "channel", "type")
    
    # keep only signals from access points
    offline = offline[offline$type == "3", ]
    
    # drop scanMac, posZ, channel, and type - no info in them
    dropVars = c("scanMac", "posZ", "channel", "type")
    offline = offline[, !(names(offline) %in% dropVars)]
    
    # drop more unwanted access points
    offline = offline[offline$mac %in% subMacs, ]
    
    # convert numeric values
    numVars = c("time", "posX", "posY", "orientation", "signal")
    offline[numVars] = lapply(offline[numVars], as.numeric)
    
    # convert time to POSIX
    offline$rawTime = offline$time
    offline$time = offline$time/1000
    class(offline$time) = c("POSIXt", "POSIXct")
    
    # round orientations to nearest 45
    offline$angle = roundOrientation(offline$orientation)
    
    return(offline)
}
offline <- readData("offline.final.trace.txt")
```

We can view the basic structure of the formatted data in the table below:


```r
offline
```

<div data-pagedtable="false">
  <script data-pagedtable-source type="application/json">
  </script>
</div>

Nolan and Lang collected data from a total of 7 access points: five Linksys routers and two Alpha routers. However, their analysis only contained information from the Linksys routers and a single Alpha router (6 routers in total). They chose to keep information from the router at MAC address `00:0f:a3:39:e1:c0`, which we will refer to as ***Router A***, and discard information from the router at MAC address `00:0f:a3:39:dd:cd`, referred to as ***Router B***. In this study, we will determine whether or not Nolan and Lang were justified in their choice to discard router B, and attempt to understand why that choice was made.

# Analysis

We performed a two-fold analysis of the data and the two routers. First, a visual and numerical analysis of the signal quality at all routers, with a focus on routers A and B. Second, we performed an analysis of the predictive power of the signal from the routers. This analysis was conducted using the K-nearest neighbors algorithm. First, a KNN analysis using all the data except that from router B, just as Nolan and Lang conducted. Second, a KNN analysis excluding router A. Third, a KNN analysis including all routers, and finally, an attempt to improve on Nolan and Lang was made, performing a weighted KNN analysis of the data. The results of these four trials were compared in order to determine A) whether or not router B should have been excluded and B) if an improvement could be made on Nolan and Lang's analysis.

## Exploratory Analysis


```r
router_b <- "00:0f:a3:39:dd:cd"
router_a <- "00:0f:a3:39:e1:c0"
fixfonts <- theme(text = element_text(family = "serif", , face = "bold"))
plt_theme <- ggthemes::theme_hc() + fixfonts
```

### Signal Strength vs Angle

As we are determining the position of the item in question from what comes down to a signal strength and an angle, it is important first to look at the relationship between signal strength and angle. In the figure below, we  examine the general relationship between signal strength and angle by holding the position fixed:


```r
offline %>% mutate(angle = factor(angle)) %>% filter(posX == 2 & posY == 12) %>% 
    ggplot + geom_boxplot(aes(y = signal, x = angle)) + facet_wrap(. ~ mac, 
    ncol = 2) + ggtitle("Boxplot of Signal vs Angle at All MAC Addresses") + 
    plt_theme
```

<div class="figure" style="text-align: center">
<img src="final_submission_ccad_files/figure-html/all_box-1.svg" alt="**Signal Strength vs Angle**: *We see that in general the signal strength follows a sinusoidal pattern as the angles are rotated through. This is not surprising*"  />
<p class="caption">**Signal Strength vs Angle**: *We see that in general the signal strength follows a sinusoidal pattern as the angles are rotated through. This is not surprising*</p>
</div>

This plot does not tell us anything that common sense would not: as we rotate through angles, the signal strength varies sinusoidally. This is because the sensor will either be pointed towards or away from the router. If we examine router B (top left), we get some sense of why Nolan and Lang preferred router A (top right). Router B has one of the weakest signals of all the routers, and contains the most outliers, which would likely make KNN analysis tricky (KNN is severely affected by outliers). Let us examine the differences between routers A and B more closely:


```r
offline %>% mutate(angle = factor(angle)) %>% filter(posX == 2 & posY == 12 & 
    mac %in% c(router_a, router_b)) %>% ggplot() + geom_boxplot(aes(y = signal, 
    x = angle)) + facet_wrap(. ~ mac, ncol = 1) + ggtitle("Signal vs Angle for a fixed position at selected MACS") + 
    plt_theme
```

<div class="figure" style="text-align: center">
<img src="final_submission_ccad_files/figure-html/box2-1.svg" alt="*Router B has much weaker signal than Router A*"  />
<p class="caption">*Router B has much weaker signal than Router A*</p>
</div>

This shows the previously made point with greater detail: the signal from router B is weak and contains many outliers. Lets affirm this by examining a table of average signal strenghth across angles and standard deviation of signal across all angles:


```r
offline %>% mutate(angle = factor(angle)) %>% group_by(mac) %>% summarise(signal_avg = mean(signal), 
    signal_std = sd(signal))
```

<div data-pagedtable="false">
  <script data-pagedtable-source type="application/json">
{"columns":[{"label":["mac"],"name":[1],"type":["chr"],"align":["left"]},{"label":["signal_avg"],"name":[2],"type":["dbl"],"align":["right"]},{"label":["signal_std"],"name":[3],"type":["dbl"],"align":["right"]}],"data":[{"1":"00:0f:a3:39:dd:cd","2":"-70","3":"8.1"},{"1":"00:0f:a3:39:e1:c0","2":"-54","3":"5.8"},{"1":"00:14:bf:3b:c7:c6","2":"-61","3":"7.1"},{"1":"00:14:bf:b1:97:81","2":"-56","3":"8.1"},{"1":"00:14:bf:b1:97:8a","2":"-57","3":"9.5"},{"1":"00:14:bf:b1:97:8d","2":"-54","3":"8.3"},{"1":"00:14:bf:b1:97:90","2":"-67","3":"10.6"}],"options":{"columns":{"min":{},"max":[10]},"rows":{"min":[10],"max":[10]},"pages":{}}}
  </script>
</div>

Again we see that router B has the weakest signal, however it is not clear that it is significantly weak, given all of the router's relatively wide standard deviations. Although the plots tell one story, this raises question to Nolan and Lang's choice of ignoring router B, it does not seem **too** different from the other routers.

### Signal Strength Distribution

Next, we decided to closely examine the distribution of the signal at each angle at each router. This will show us how easily separable, or identifiable, each angle is at the router, which could be related to how easy it is to determine the position of the router from the underlying signal (triangles and cosines tell us angles are related to signals). Let us first examine the signal distribution at all MAC addresses:


```r
offline %>% mutate(angle = factor(angle)) %>% filter(posX == 2 & posY == 12) %>% 
    ggplot(aes(signal, fill = angle)) + geom_density() + facet_wrap(. ~ mac, 
    ncol = 1) + ggtitle("Per Angle Signal Density at the Two MACS") + plt_theme + 
    scale_fill_viridis_d()
```

<div class="figure" style="text-align: center">
<img src="final_submission_ccad_files/figure-html/all_dens-1.svg" alt="**Signal Density Plots**: *We see that for most routers, the angle creates clearly separate distributions, which should lead to easy position determination, however for router B this is not the case.*"  />
<p class="caption">**Signal Density Plots**: *We see that for most routers, the angle creates clearly separate distributions, which should lead to easy position determination, however for router B this is not the case.*</p>
</div>

From this, we again see the weakness of the signal at router B. We can also note that the distributions of signal at each angle cover each other up almost completely at router B (except at 90 degrees). This does not bode well for being able to extract the position or angle from the signal data, and makes another point towards Nolan and Lang's exclusion of the router. Let us now compare the signal distributions for just routers A and B:


```r
offline %>% mutate(angle = factor(angle)) %>% filter(posX == 2 & posY == 12 & 
    mac %in% c(router_a, router_b)) %>% ggplot(aes(signal, fill = angle)) + 
    geom_density() + facet_wrap(. ~ mac, ncol = 1) + ggtitle("Per Angle Signal Density at the Two MACS") + 
    plt_theme + scale_fill_viridis_d()
```

<div class="figure" style="text-align: center">
<img src="final_submission_ccad_files/figure-html/two_dens-1.svg" alt="*Our previous observations hold true, the signal is significantly weaker at router B (*top*) than router A (*bottom*). It is also not apparent that the signals from router B come from separate distributions*"  />
<p class="caption">*Our previous observations hold true, the signal is significantly weaker at router B (*top*) than router A (*bottom*). It is also not apparent that the signals from router B come from separate distributions*</p>
</div>

Router B (top) has a much weaker overall signal than router A, and the distributions of the signal do not appear to change too much with angle, in contrast to the clear change with angle at router A. The authors of this report believe that this was sufficient reason for Nolan and Lang to excluder router B. It is now time to test the correctness of Nolan and Lang's choice through practical analysis. For more detailed, but less pertinent visualizations of the data, please refer to Nolan and Lang's chapter on the subject.

## Practical Analysis

### K Nearest Neighbours Excluding Router B

First, we will conduct a KNN analysis following Nolan and Lang, by excluding router B. This will serve as a baseline for us to test against. First, we will run a grid search to determine the best value of K. Below, we show the plot of the sum of squares error versus K in our search:


```r
offline <- readData("offline.final.trace.txt")
# fix up the xypos
offline$posXY <- paste(offline$posX, offline$posY, sep = "-")
byLocAngleAP = with(offline, by(offline, list(posXY, angle, mac), function(x) x))

signalSummary = lapply(byLocAngleAP, function(oneLoc) {
    ans = oneLoc[1, ]
    ans$medSignal = median(oneLoc$signal)
    ans$avgSignal = mean(oneLoc$signal)
    ans$num = length(oneLoc$signal)
    ans$sdSignal = sd(oneLoc$signal)
    ans$iqrSignal = IQR(oneLoc$signal)
    ans
})
offlineSummary_original = do.call("rbind", signalSummary)
offlineSummary <- offlineSummary_original %>% filter(mac != router_b)

online <- readData("online.final.trace.txt", subMacs = unique(offlineSummary$mac))
online$posXY <- paste(online$posX, online$posY, sep = "-")

keepVars = c("posXY", "posX", "posY", "orientation", "angle")
byLoc = with(online, by(online, list(posXY), function(x) {
    ans = x[1, keepVars]
    avgSS = tapply(x$signal, x$mac, mean)
    y = matrix(avgSS, nrow = 1, ncol = 6, dimnames = list(ans$posXY, names(avgSS)))
    cbind(ans, y)
}))

onlineSummary = do.call("rbind", byLoc)
calcError <- function(estXY, actualXY) sum(rowSums((estXY - actualXY)^2))

reshapeSS1 <- function(data, varSignal = "signal", keepVars = c("posXY", "posX", 
    "posY")) {
    byLocation <- with(data, by(data, list(posXY), function(x) {
        ans <- x[1, keepVars]
        avgSS <- tapply(x[, varSignal], x$mac, mean)
        y <- matrix(avgSS, nrow = 1, ncol = 6, dimnames = list(ans$posXY, names(avgSS)))
        cbind(ans, y)
    }))
    
    newDataSS <- do.call("rbind", byLocation)
    return(newDataSS)
}


selectTrain1 <- function(angleNewObs, signals = NULL, m = 1) {
    # m is the number of angles to keep between 1 and 5
    refs <- seq(0, by = 45, length = 8)
    nearestAngle <- roundOrientation(angleNewObs)
    
    if (m%%2 == 1) 
        angles <- seq(-45 * (m - 1)/2, 45 * (m - 1)/2, length = m) else {
        m = m + 1
        angles <- seq(-45 * (m - 1)/2, 45 * (m - 1)/2, length = m)
        if (sign(angleNewObs - nearestAngle) > -1) 
            angles <- angles[-1] else angles <- angles[-m]
    }
    # round angles
    angles <- angles + nearestAngle
    angles[angles < 0] <- angles[angles < 0] + 360
    angles[angles > 360] <- angles[angles > 360] - 360
    angles <- sort(angles)
    
    offlineSubset <- signals[signals$angle %in% angles, ]
    reshapeSS1(offlineSubset, varSignal = "avgSignal")
}


findNN1 <- function(newSignal, trainSubset) {
    diffs <- apply(trainSubset[, 4:9], 1, function(x) x - newSignal)
    dists <- apply(diffs, 2, function(x) sqrt(sum(x^2)))
    closest <- order(dists)
    weightDF <- trainSubset[closest, 1:3]
    weightDF$weight <- 1/closest
    return(weightDF)
}


predXY1 <- function(newSignals, newAngles, trainData, numAngles = 1, k = 3) {
    closeXY <- list(length = nrow(newSignals))
    
    for (i in 1:nrow(newSignals)) {
        trainSS <- selectTrain1(newAngles[i], trainData, m = numAngles)
        closeXY[[i]] <- findNN1(newSignal = as.numeric(newSignals[i, ]), trainSS)
    }
    
    estXY <- lapply(closeXY, function(x) sapply(x[, 2:3], function(x) mean(x[1:k])))
    estXY <- do.call("rbind", estXY)
    return(estXY)
}


v = 11
permuteLocs = sample(unique(offlineSummary$posXY))
permuteLocs = matrix(permuteLocs, ncol = v, nrow = floor(length(permuteLocs)/v))

onlineFold = subset(offlineSummary, posXY %in% permuteLocs[, 1])
reshapeSS1 = function(data, varSignal = "signal", keepVars = c("posXY", "posX", 
    "posY"), sampleAngle = FALSE, refs = seq(0, 315, by = 45)) {
    byLocation = with(data, by(data, list(posXY), function(x) {
        if (sampleAngle) {
            x = x[x$angle == sample(refs, size = 1), ]
        }
        ans = x[1, keepVars]
        avgSS = tapply(x[, varSignal], x$mac, mean)
        y = matrix(avgSS, nrow = 1, ncol = 6, dimnames = list(ans$posXY, names(avgSS)))
        cbind(ans, y)
    }))
    
    newDataSS = do.call("rbind", byLocation)
    return(newDataSS)
}


offline = offline[offline$mac != "00:0f:a3:39:dd:cd", ]

keepVars = c("posXY", "posX", "posY", "orientation", "angle")

onlineCVSummary = reshapeSS1(offline, keepVars = keepVars, sampleAngle = TRUE)

onlineFold = subset(onlineCVSummary, posXY %in% permuteLocs[, 1])

offlineFold = subset(offlineSummary, posXY %in% permuteLocs[, -1])

estFold = predXY1(newSignals = onlineFold[, 6:11], newAngles = onlineFold[, 
    4], offlineFold, numAngles = 1, k = 3)

actualFold = onlineFold[, c("posX", "posY")]

NNeighbors = 20
K = NNeighbors
err = numeric(K)

for (j in 1:v) {
    onlineFold = subset(onlineCVSummary, posXY %in% permuteLocs[, j])
    offlineFold = subset(offlineSummary, posXY %in% permuteLocs[, -j])
    actualFold = onlineFold[, c("posX", "posY")]
    
    for (k in 1:K) {
        estFold = predXY1(newSignals = onlineFold[, 6:11], newAngles = onlineFold[, 
            4], offlineFold, numAngles = 1, k = k)
        err[k] = err[k] + calcError(estFold, actualFold)
    }
}

errdf <- data.frame(router_a = err)
plot(y = err, x = (1:K), type = "l", lwd = 2, ylim = c(800, 2100), xlab = "Number of Neighbors", 
    ylab = "Sum of Square Errors", main = "Error vs K, with Router A Data")

rmseMin = min(err)
kMin = which(err == rmseMin)[1]
segments(x0 = 0, x1 = kMin, y0 = rmseMin, col = gray(0.4), lty = 2, lwd = 2)
segments(x0 = kMin, x1 = kMin, y0 = 1100, y1 = rmseMin, col = grey(0.4), lty = 2, 
    lwd = 2)

# mtext(kMin, side = 1, line = 1, at = kMin, col = grey(0.4))
text(x = kMin - 2, y = rmseMin + 40, label = as.character(round(rmseMin)), col = grey(0.4))
```

<img src="final_submission_ccad_files/figure-html/search-1.svg" style="display: block; margin: auto;" />

```r
estXYkmin1 = predXY1(newSignals = onlineSummary[, 6:11], newAngles = onlineSummary[, 
    4], offlineSummary, numAngles = 1, k = kMin)
actualXY = onlineSummary[, c("posX", "posY")]
err_cv1 <- calcError(estXYkmin1, actualXY)
trainPoints = offlineSummary[offlineSummary$angle == 0 & offlineSummary$mac == 
    "00:0f:a3:39:e1:c0", c("posX", "posY")]


floorErrorMap = function(estXY, actualXY, trainPoints = NULL, AP = NULL) {
    
    plot(0, 0, xlim = c(0, 35), ylim = c(-3, 15), type = "n", xlab = "", ylab = "", 
        axes = FALSE, main = "Floor Map of Predictions", sub = "■ = Access Point, ● = Actual, ✷ = Predicted")
    box()
    if (!is.null(AP)) 
        points(AP, pch = 15)
    if (!is.null(trainPoints)) 
        points(trainPoints, pch = 19, col = "grey", cex = 0.6)
    
    points(x = actualXY[, 1], y = actualXY[, 2], pch = 19, cex = 0.8)
    points(x = estXY[, 1], y = estXY[, 2], pch = 8, cex = 0.8)
    segments(x0 = estXY[, 1], y0 = estXY[, 2], x1 = actualXY[, 1], y1 = actualXY[, 
        2], lwd = 2, col = "red")
}


actualXY = onlineSummary[, c("posX", "posY")]
```

Looks like the best value for K was about 5, with an error of 1365.6. We can use cross validated value of K to make a prediction on the online data, which has an RMSE of  417.18. We will see how this stacks up compared to the others. Let us now turn our attention to router B:


### K Nearest Neighbours Excluding Router A

Now we will diverge from the work of Nolan and Lang, and exclude router A. Again, we will first run a grid search of K, displaying the 11-fold cross-validated error below:


```r
offline <- readData("offline.final.trace.txt")
# fix up the xypos
offline$posXY <- paste(offline$posX, offline$posY, sep = "-")
byLocAngleAP = with(offline, by(offline, list(posXY, angle, mac), function(x) x))

signalSummary = lapply(byLocAngleAP, function(oneLoc) {
    ans = oneLoc[1, ]
    ans$medSignal = median(oneLoc$signal)
    ans$avgSignal = mean(oneLoc$signal)
    ans$num = length(oneLoc$signal)
    ans$sdSignal = sd(oneLoc$signal)
    ans$iqrSignal = IQR(oneLoc$signal)
    ans
})
offlineSummary_original = do.call("rbind", signalSummary)
offlineSummary <- offlineSummary_original %>% filter(mac != router_a)

online <- readData("online.final.trace.txt", subMacs = unique(offlineSummary$mac))
online$posXY <- paste(online$posX, online$posY, sep = "-")

keepVars = c("posXY", "posX", "posY", "orientation", "angle")
byLoc = with(online, by(online, list(posXY), function(x) {
    ans = x[1, keepVars]
    avgSS = tapply(x$signal, x$mac, mean)
    y = matrix(avgSS, nrow = 1, ncol = 6, dimnames = list(ans$posXY, names(avgSS)))
    cbind(ans, y)
}))

onlineSummary = do.call("rbind", byLoc)


v = 11
permuteLocs = sample(unique(offlineSummary$posXY))
permuteLocs = matrix(permuteLocs, ncol = v, nrow = floor(length(permuteLocs)/v))

onlineFold = subset(offlineSummary, posXY %in% permuteLocs[, 1])


offline = offline[offline$mac != router_a, ]

keepVars = c("posXY", "posX", "posY", "orientation", "angle")

onlineCVSummary = reshapeSS1(offline, keepVars = keepVars, sampleAngle = TRUE)

onlineFold = subset(onlineCVSummary, posXY %in% permuteLocs[, 1])

offlineFold = subset(offlineSummary, posXY %in% permuteLocs[, -1])

estFold = predXY1(newSignals = onlineFold[, 6:11], newAngles = onlineFold[, 
    4], offlineFold, numAngles = 1, k = 3)

actualFold = onlineFold[, c("posX", "posY")]

NNeighbors = 20
K = NNeighbors
err = numeric(K)

for (j in 1:v) {
    onlineFold = subset(onlineCVSummary, posXY %in% permuteLocs[, j])
    offlineFold = subset(offlineSummary, posXY %in% permuteLocs[, -j])
    actualFold = onlineFold[, c("posX", "posY")]
    
    for (k in 1:K) {
        estFold = predXY1(newSignals = onlineFold[, 6:11], newAngles = onlineFold[, 
            4], offlineFold, numAngles = 1, k = k)
        err[k] = err[k] + calcError(estFold, actualFold)
    }
}

errdf$router_b <- err
plot(y = err, x = (1:K), type = "l", lwd = 2, ylim = c(800, 2100), xlab = "Number of Neighbors", 
    ylab = "Sum of Square Errors", main = "Error vs K, with Router B Data")

rmseMin = min(err)
kMin = which(err == rmseMin)[1]
segments(x0 = 0, x1 = kMin, y0 = rmseMin, col = gray(0.4), lty = 2, lwd = 2)
segments(x0 = kMin, x1 = kMin, y0 = 1100, y1 = rmseMin, col = grey(0.4), lty = 2, 
    lwd = 2)

# mtext(kMin, side = 1, line = 1, at = kMin, col = grey(0.4))
text(x = kMin - 2, y = rmseMin + 40, label = as.character(round(rmseMin)), col = grey(0.4))
```

<img src="final_submission_ccad_files/figure-html/search2-1.svg" style="display: block; margin: auto;" />

```r
estXYkmin2 = predXY1(newSignals = onlineSummary[, 6:11], newAngles = onlineSummary[, 
    4], offlineSummary, numAngles = 1, k = kMin)


actualXY = onlineSummary[, c("posX", "posY")]
err_cv2 <- calcError(estXYkmin2, actualXY)

trainPoints = offlineSummary[offlineSummary$angle == 0 & offlineSummary$mac == 
    "00:0f:a3:39:e1:c0", c("posX", "posY")]


floorErrorMap = function(estXY, actualXY, trainPoints = NULL, AP = NULL) {
    
    plot(0, 0, xlim = c(0, 35), ylim = c(-3, 15), type = "n", xlab = "", ylab = "", 
        axes = FALSE, main = "Floor Map of Predictions", sub = "■ = Access Point, ● = Actual, ✷ = Predicted")
    box()
    if (!is.null(AP)) 
        points(AP, pch = 15)
    if (!is.null(trainPoints)) 
        points(trainPoints, pch = 19, col = "grey", cex = 0.6)
    
    points(x = actualXY[, 1], y = actualXY[, 2], pch = 19, cex = 0.8)
    points(x = estXY[, 1], y = estXY[, 2], pch = 8, cex = 0.8)
    segments(x0 = estXY[, 1], y0 = estXY[, 2], x1 = actualXY[, 1], y1 = actualXY[, 
        2], lwd = 2, col = "red")
}

actualXY = onlineSummary[, c("posX", "posY")]
```

Looks like the best value for K was about  5, with an error of  1119.56. We can use cross validated value of K to make a prediction on the online data, which has an RMSE of  290.89. Lets compare the results to those of router B:


```r
errdf$k <- 1:nrow(errdf)
errdf %>% gather_("Router", "RMSE", names(errdf)[-length(errdf)]) %>% ggplot() + 
    geom_line(aes(x = k, y = RMSE, color = Router)) + plt_theme + ggtitle("RMSE Over K by Router Subset")
```

<div class="figure" style="text-align: center">
<img src="final_submission_ccad_files/figure-html/unnamed-chunk-3-1.svg" alt="*Router B overall performed better than Router A*"  />
<p class="caption">*Router B overall performed better than Router A*</p>
</div>

This represents a major blow to Nolan and Lang's case: the dataset using Router B (which they excluded) performed significantly better than the dataset using Router A in its stead. The table below puts this to numbers:


```r
data.frame(router = c("router a", "router b"), `online Sum of Square errors` = c(err_cv1, 
    err_cv2))
```

<div data-pagedtable="false">
  <script data-pagedtable-source type="application/json">
{"columns":[{"label":["router"],"name":[1],"type":["fctr"],"align":["left"]},{"label":["online.Sum.of.Square.errors"],"name":[2],"type":["dbl"],"align":["right"]}],"data":[{"1":"router a","2":"417"},{"1":"router b","2":"291"}],"options":{"columns":{"min":{},"max":[10]},"rows":{"min":[10],"max":[10]},"pages":{}}}
  </script>
</div>

In a practical setting, in its own right Router B is more informative than Router A! We will now expand our analysis to all of the data.


### K Nearest Neighbours Using All Routers

Now we will diverge from the work of Nolan and Lang, and exclude router A. Again, we will first run a grid search of K, displaying the 11-fold cross-validated error below:




```r
offline <- readData("offline.final.trace.txt")
# fix up the xypos
offline$posXY <- paste(offline$posX, offline$posY, sep = "-")
byLocAngleAP = with(offline, by(offline, list(posXY, angle, mac), function(x) x))

signalSummary = lapply(byLocAngleAP, function(oneLoc) {
    ans = oneLoc[1, ]
    ans$medSignal = median(oneLoc$signal)
    ans$avgSignal = mean(oneLoc$signal)
    ans$num = length(oneLoc$signal)
    ans$sdSignal = sd(oneLoc$signal)
    ans$iqrSignal = IQR(oneLoc$signal)
    ans
})
offlineSummary = do.call("rbind", signalSummary)

online <- readData("online.final.trace.txt", subMacs = unique(offlineSummary$mac))
online$posXY <- paste(online$posX, online$posY, sep = "-")

keepVars = c("posXY", "posX", "posY", "orientation", "angle")
byLoc = with(online, by(online, list(posXY), function(x) {
    ans = x[1, keepVars]
    avgSS = tapply(x$signal, x$mac, mean)
    y = matrix(avgSS, nrow = 1, ncol = 7, dimnames = list(ans$posXY, names(avgSS)))
    cbind(ans, y)
}))

onlineSummary = do.call("rbind", byLoc)
calcError <- function(estXY, actualXY) sum(rowSums((estXY - actualXY)^2))

reshapeSS2 <- function(data, varSignal = "signal", keepVars = c("posXY", "posX", 
    "posY")) {
    byLocation <- with(data, by(data, list(posXY), function(x) {
        ans <- x[1, keepVars]
        avgSS <- tapply(x[, varSignal], x$mac, mean)
        y <- matrix(avgSS, nrow = 1, ncol = 7, dimnames = list(ans$posXY, names(avgSS)))
        cbind(ans, y)
    }))
    
    newDataSS <- do.call("rbind", byLocation)
    return(newDataSS)
}


selectTrain2 <- function(angleNewObs, signals = NULL, m = 1) {
    # m is the number of angles to keep between 1 and 5
    refs <- seq(0, by = 45, length = 8)
    nearestAngle <- roundOrientation(angleNewObs)
    
    if (m%%2 == 1) 
        angles <- seq(-45 * (m - 1)/2, 45 * (m - 1)/2, length = m) else {
        m = m + 1
        angles <- seq(-45 * (m - 1)/2, 45 * (m - 1)/2, length = m)
        if (sign(angleNewObs - nearestAngle) > -1) 
            angles <- angles[-1] else angles <- angles[-m]
    }
    # round angles
    angles <- angles + nearestAngle
    angles[angles < 0] <- angles[angles < 0] + 360
    angles[angles > 360] <- angles[angles > 360] - 360
    angles <- sort(angles)
    
    offlineSubset <- signals[signals$angle %in% angles, ]
    reshapeSS2(offlineSubset, varSignal = "avgSignal")
}


findNN2 <- function(newSignal, trainSubset) {
    diffs <- apply(trainSubset[, 4:9], 1, function(x) x - newSignal)
    dists <- apply(diffs, 2, function(x) sqrt(sum(x^2)))
    closest <- order(dists)
    weightDF <- trainSubset[closest, 1:3]
    weightDF$weight <- 1/closest
    return(weightDF)
}


predXY2 <- function(newSignals, newAngles, trainData, numAngles = 1, k = 3) {
    closeXY <- list(length = nrow(newSignals))
    
    for (i in 1:nrow(newSignals)) {
        trainSS <- selectTrain2(newAngles[i], trainData, m = numAngles)
        closeXY[[i]] <- findNN2(newSignal = as.numeric(newSignals[i, ]), trainSS)
    }
    
    estXY <- lapply(closeXY, function(x) sapply(x[, 2:3], function(x) mean(x[1:k])))
    estXY <- do.call("rbind", estXY)
    return(estXY)
}


v = 11
permuteLocs = sample(unique(offlineSummary$posXY))
permuteLocs = matrix(permuteLocs, ncol = v, nrow = floor(length(permuteLocs)/v))

onlineFold = subset(offlineSummary, posXY %in% permuteLocs[, 1])
reshapeSS2 = function(data, varSignal = "signal", keepVars = c("posXY", "posX", 
    "posY"), sampleAngle = FALSE, refs = seq(0, 315, by = 45)) {
    byLocation = with(data, by(data, list(posXY), function(x) {
        if (sampleAngle) {
            x = x[x$angle == sample(refs, size = 1), ]
        }
        ans = x[1, keepVars]
        avgSS = tapply(x[, varSignal], x$mac, mean)
        y = matrix(avgSS, nrow = 1, ncol = 7, dimnames = list(ans$posXY, names(avgSS)))
        cbind(ans, y)
    }))
    
    newDataSS = do.call("rbind", byLocation)
    return(newDataSS)
}


keepVars = c("posXY", "posX", "posY", "orientation", "angle")

onlineCVSummary = reshapeSS2(offline, keepVars = keepVars, sampleAngle = TRUE)

onlineFold = subset(onlineCVSummary, posXY %in% permuteLocs[, 1])

offlineFold = subset(offlineSummary, posXY %in% permuteLocs[, -1])

estFold = predXY2(newSignals = onlineFold[, 6:12], newAngles = onlineFold[, 
    5], offlineFold, numAngles = 1, k = 3)

actualFold = onlineFold[, c("posX", "posY")]

NNeighbors = 20
K = NNeighbors
err = numeric(K)

for (j in 1:v) {
    onlineFold = subset(onlineCVSummary, posXY %in% permuteLocs[, j])
    offlineFold = subset(offlineSummary, posXY %in% permuteLocs[, -j])
    actualFold = onlineFold[, c("posX", "posY")]
    
    for (k in 1:K) {
        estFold = predXY2(newSignals = onlineFold[, 6:11], newAngles = onlineFold[, 
            4], offlineFold, numAngles = 1, k = k)
        err[k] = err[k] + calcError(estFold, actualFold)
    }
}

errdf$both <- err
plot(y = err, x = (1:K), type = "l", lwd = 2, ylim = c(800, 2100), xlab = "Number of Neighbors", 
    ylab = "Sum of Square Errors", main = "Error vs K, with all Data")

rmseMin = min(err)
kMin = which(err == rmseMin)[1]
segments(x0 = 0, x1 = kMin, y0 = rmseMin, col = gray(0.4), lty = 2, lwd = 2)
segments(x0 = kMin, x1 = kMin, y0 = 1100, y1 = rmseMin, col = grey(0.4), lty = 2, 
    lwd = 2)

# mtext(kMin, side = 1, line = 1, at = kMin, col = grey(0.4))
text(x = kMin - 2, y = rmseMin + 40, label = as.character(round(rmseMin)), col = grey(0.4))
```

<img src="final_submission_ccad_files/figure-html/search3-1.svg" style="display: block; margin: auto;" />

```r
estXYkmin3 = predXY2(newSignals = onlineSummary[, 6:12], newAngles = onlineSummary[, 
    5], offlineSummary, numAngles = 1, k = kMin)
actualXY = onlineSummary[, c("posX", "posY")]
err_cv3 <- calcError(estXYkmin3, actualXY)

trainPoints = offlineSummary[offlineSummary$angle == 0 & offlineSummary$mac == 
    "00:0f:a3:39:e1:c0", c("posX", "posY")]


floorErrorMap = function(estXY, actualXY, trainPoints = NULL, AP = NULL) {
    
    plot(0, 0, xlim = c(0, 35), ylim = c(-3, 15), type = "n", xlab = "", ylab = "", 
        axes = FALSE, main = "Floor Map of Predictions", sub = "■ = Access Point, ● = Actual, ✷ = Predicted")
    box()
    if (!is.null(AP)) 
        points(AP, pch = 15)
    if (!is.null(trainPoints)) 
        points(trainPoints, pch = 19, col = "grey", cex = 0.6)
    
    points(x = actualXY[, 1], y = actualXY[, 2], pch = 19, cex = 0.8)
    points(x = estXY[, 1], y = estXY[, 2], pch = 8, cex = 0.8)
    segments(x0 = estXY[, 1], y0 = estXY[, 2], x1 = actualXY[, 1], y1 = actualXY[, 
        2], lwd = 2, col = "red")
}


actualXY = onlineSummary[, c("posX", "posY")]
```


Looks like the best value for K was about  3, with an error of  1498.56. We can use cross validated value of K to make a prediction on the online data, which has an RMSE of  455.79. Lets compare to our previous results:


```r
errdf %>% gather_("Router", "RMSE", names(errdf)[-(length(errdf) - 1)]) %>% 
    ggplot() + geom_line(aes(x = k, y = RMSE, color = Router)) + plt_theme + 
    ggtitle("RMSE Over K by Router Subset")
```

<div class="figure" style="text-align: center">
<img src="final_submission_ccad_files/figure-html/unnamed-chunk-5-1.svg" alt="*Adding Router A into the mix makes the model perform notably worse*"  />
<p class="caption">*Adding Router A into the mix makes the model perform notably worse*</p>
</div>

With this, we can say conclusively that Router B, excluded by Nolan and Lang, is a better choice for this RTLS system. We can again demonstrate this numerically with a table:



```r
data.frame(router = c("router a", "router b", "both"), `Online sum of squares` = c(err_cv1, 
    err_cv2, err_cv3))
```

<div data-pagedtable="false">
  <script data-pagedtable-source type="application/json">
{"columns":[{"label":["router"],"name":[1],"type":["fctr"],"align":["left"]},{"label":["Online.sum.of.squares"],"name":[2],"type":["dbl"],"align":["right"]}],"data":[{"1":"router a","2":"417"},{"1":"router b","2":"291"},{"1":"both","2":"456"}],"options":{"columns":{"min":{},"max":[10]},"rows":{"min":[10],"max":[10]},"pages":{}}}
  </script>
</div>

Lets see if we can bump our best results even lower by performing a weighted KNN analysis.

### Weighted KNN Analysis

To "weight" our K nearest neighbors algorithm, we have to make a simple adjustment to the




```r
offline <- readData("offline.final.trace.txt")
# fix up the xypos
offline$posXY <- paste(offline$posX, offline$posY, sep = "-")
byLocAngleAP = with(offline, by(offline, list(posXY, angle, mac), function(x) x))

signalSummary = lapply(byLocAngleAP, function(oneLoc) {
    ans = oneLoc[1, ]
    ans$medSignal = median(oneLoc$signal)
    ans$avgSignal = mean(oneLoc$signal)
    ans$num = length(oneLoc$signal)
    ans$sdSignal = sd(oneLoc$signal)
    ans$iqrSignal = IQR(oneLoc$signal)
    ans
})
offlineSummary_original = do.call("rbind", signalSummary)
offlineSummary <- offlineSummary_original %>% filter(mac != router_a)

online <- readData("online.final.trace.txt", subMacs = unique(offlineSummary$mac))
online$posXY <- paste(online$posX, online$posY, sep = "-")

keepVars = c("posXY", "posX", "posY", "orientation", "angle")
byLoc = with(online, by(online, list(posXY), function(x) {
    ans = x[1, keepVars]
    avgSS = tapply(x$signal, x$mac, mean)
    y = matrix(avgSS, nrow = 1, ncol = 6, dimnames = list(ans$posXY, names(avgSS)))
    cbind(ans, y)
}))

onlineSummary = do.call("rbind", byLoc)
calcError <- function(estXY, actualXY) sum(rowSums((estXY - actualXY)^2))

reshapeSS1 <- function(data, varSignal = "signal", keepVars = c("posXY", "posX", 
    "posY")) {
    byLocation <- with(data, by(data, list(posXY), function(x) {
        ans <- x[1, keepVars]
        avgSS <- tapply(x[, varSignal], x$mac, mean)
        y <- matrix(avgSS, nrow = 1, ncol = 6, dimnames = list(ans$posXY, names(avgSS)))
        cbind(ans, y)
    }))
    
    newDataSS <- do.call("rbind", byLocation)
    return(newDataSS)
}


selectTrain1 <- function(angleNewObs, signals = NULL, m = 1) {
    # m is the number of angles to keep between 1 and 5
    refs <- seq(0, by = 45, length = 8)
    nearestAngle <- roundOrientation(angleNewObs)
    
    if (m%%2 == 1) 
        angles <- seq(-45 * (m - 1)/2, 45 * (m - 1)/2, length = m) else {
        m = m + 1
        angles <- seq(-45 * (m - 1)/2, 45 * (m - 1)/2, length = m)
        if (sign(angleNewObs - nearestAngle) > -1) 
            angles <- angles[-1] else angles <- angles[-m]
    }
    # round angles
    angles <- angles + nearestAngle
    angles[angles < 0] <- angles[angles < 0] + 360
    angles[angles > 360] <- angles[angles > 360] - 360
    angles <- sort(angles)
    
    offlineSubset <- signals[signals$angle %in% angles, ]
    reshapeSS1(offlineSubset, varSignal = "avgSignal")
}


findNN_weighted = function(newSignal, trainSubset) {
    diffs = apply(trainSubset[, 4:9], 1, function(x) x - newSignal)
    dists <- sqrt(colSums(diffs^2))  # why is the book using apply when R is vectorized?
    weighted_dists <- (1/dists)/(sum(1/dists))
    closest = order(dists)
    return(list(trainSubset[closest, 1:3], (1/dists)[order(weighted_dists, decreasing = TRUE)]))
}


library(foreach)
library(doParallel)
cl <- makeCluster(parallel::detectCores() - 1)
registerDoParallel(cl)
predXY_weighted = function(newSignals, newAngles, trainData, numAngles = 1, 
    k = 3) {
    l <- nrow(newSignals)
    res <- foreach(i = 1:nrow(newSignals)) %do% {
        trainSS <- selectTrain1(newAngles[i], trainData, m = numAngles)
        nn <- findNN_weighted(newSignal = as.numeric(newSignals[i, ]), trainSS)[[1]]
        wdist <- findNN_weighted(newSignal = as.numeric(newSignals[i, ]), trainSS)[[2]]
        weighted_dist <- wdist[1:k]/sum(wdist[1:k])
        lab <- as.matrix(nn[1:k, 2:3] * weighted_dist)
        return(lab)
    }
    estXY = lapply(res, colSums)
    estXY = do.call("rbind", estXY)
    return(estXY)
}

v = 11
permuteLocs = sample(unique(offlineSummary$posXY))
permuteLocs = matrix(permuteLocs, ncol = v, nrow = floor(length(permuteLocs)/v))

onlineFold = subset(offlineSummary, posXY %in% permuteLocs[, 1])
reshapeSS1 = function(data, varSignal = "signal", keepVars = c("posXY", "posX", 
    "posY"), sampleAngle = FALSE, refs = seq(0, 315, by = 45)) {
    byLocation = with(data, by(data, list(posXY), function(x) {
        if (sampleAngle) {
            x = x[x$angle == sample(refs, size = 1), ]
        }
        ans = x[1, keepVars]
        avgSS = tapply(x[, varSignal], x$mac, mean)
        y = matrix(avgSS, nrow = 1, ncol = 6, dimnames = list(ans$posXY, names(avgSS)))
        cbind(ans, y)
    }))
    
    newDataSS = do.call("rbind", byLocation)
    return(newDataSS)
}


offline = offline[offline$mac != "00:0f:a3:39:dd:cd", ]

keepVars = c("posXY", "posX", "posY", "orientation", "angle")

onlineCVSummary = reshapeSS1(offline, keepVars = keepVars, sampleAngle = TRUE)

onlineFold = subset(onlineCVSummary, posXY %in% permuteLocs[, 1])

offlineFold = subset(offlineSummary, posXY %in% permuteLocs[, -1])

estFold = predXY_weighted(newSignals = onlineFold[, 6:11], newAngles = onlineFold[, 
    4], offlineFold, numAngles = 1, k = 3)


actualFold = onlineFold[, c("posX", "posY")]

NNeighbors = 20
K = NNeighbors
err = numeric(K)

for (j in 1:v) {
    onlineFold = subset(onlineCVSummary, posXY %in% permuteLocs[, j])
    offlineFold = subset(offlineSummary, posXY %in% permuteLocs[, -j])
    actualFold = onlineFold[, c("posX", "posY")]
    
    for (k in 1:K) {
        estFold = predXY_weighted(newSignals = onlineFold[, 6:11], newAngles = onlineFold[, 
            4], offlineFold, numAngles = 1, k = k)
        err[k] = err[k] + calcError(estFold, actualFold)
    }
}

errdf$weighted <- err
plot(y = err, x = (1:K), type = "l", lwd = 2, ylim = c(800, 8000), xlab = "Number of Neighbors", 
    ylab = "Sum of Square Errors", main = "Error vs K, with weighted Data")

rmseMin = min(err)
kMin = which(err == rmseMin)[1]
segments(x0 = 0, x1 = kMin, y0 = rmseMin, col = gray(0.4), lty = 2, lwd = 2)
segments(x0 = kMin, x1 = kMin, y0 = 1100, y1 = rmseMin, col = grey(0.4), lty = 2, 
    lwd = 2)

# mtext(kMin, side = 1, line = 1, at = kMin, col = grey(0.4))
text(x = kMin - 2, y = rmseMin + 40, label = as.character(round(rmseMin)), col = grey(0.4))
```

<img src="final_submission_ccad_files/figure-html/search4-1.svg" style="display: block; margin: auto;" />

```r
estXYkmin4 = predXY_weighted(newSignals = onlineSummary[, 6:11], newAngles = onlineSummary[, 
    4], offlineSummary, numAngles = 1, k = kMin)
actualXY = onlineSummary[, c("posX", "posY")]
err_cv4 <- calcError(estXYkmin4, actualXY)

trainPoints = offlineSummary[offlineSummary$angle == 0 & offlineSummary$mac == 
    "00:0f:a3:39:e1:c0", c("posX", "posY")]


floorErrorMap = function(estXY, actualXY, trainPoints = NULL, AP = NULL) {
    
    plot(0, 0, xlim = c(0, 35), ylim = c(-3, 15), type = "n", xlab = "", ylab = "", 
        axes = FALSE, main = "Floor Map of Predictions", sub = "■ = Access Point, ● = Actual, ✷ = Predicted")
    box()
    if (!is.null(AP)) 
        points(AP, pch = 15)
    if (!is.null(trainPoints)) 
        points(trainPoints, pch = 19, col = "grey", cex = 0.6)
    
    points(x = actualXY[, 1], y = actualXY[, 2], pch = 19, cex = 0.8)
    points(x = estXY[, 1], y = estXY[, 2], pch = 8, cex = 0.8)
    segments(x0 = estXY[, 1], y0 = estXY[, 2], x1 = actualXY[, 1], y1 = actualXY[, 
        2], lwd = 2, col = "red")
}
actualXY = onlineSummary[, c("posX", "posY")]
```


Looks like the best value for K was about  13, with an error of  5985.64. We can use cross validated value of K to make a prediction on the online data, which has an RMSE of  279.39. Lets compare to our previous results:


```r
errdf %>% gather_("Router", "RMSE", names(errdf)[-(length(errdf) - 2)]) %>% 
    ggplot() + geom_line(aes(x = k, y = RMSE, color = Router)) + plt_theme + 
    ggtitle("RMSE Over K by Router Subset")
```

<div class="figure" style="text-align: center">
<img src="final_submission_ccad_files/figure-html/unnamed-chunk-7-1.svg" alt="*The offline training errors with the weighted KNN were rather large...*"  />
<p class="caption">*The offline training errors with the weighted KNN were rather large...*</p>
</div>

Lets check out how we did on our online test set now, using the weighted knn:



```r
data.frame(router = c("router a", "router b", "both", "weighted"), `Online sum of squares` = c(err_cv1, 
    err_cv2, err_cv3, err_cv4))
```

<div data-pagedtable="false">
  <script data-pagedtable-source type="application/json">
{"columns":[{"label":["router"],"name":[1],"type":["fctr"],"align":["left"]},{"label":["Online.sum.of.squares"],"name":[2],"type":["dbl"],"align":["right"]}],"data":[{"1":"router a","2":"417"},{"1":"router b","2":"291"},{"1":"both","2":"456"},{"1":"weighted","2":"279"}],"options":{"columns":{"min":{},"max":[10]},"rows":{"min":[10],"max":[10]},"pages":{}}}
  </script>
</div>

During cross validation, the weighted KNN performed overall rather poorly, with about 3 times the RMSE of the other models. However, it performed very well on the online test set, with the lowest error overall. We will discuss our results in the next section.

# Conclusion

Our study determined that the MAC address which Nolan and Lang ignored actually significantly, and performed better than even using ALL of the data. As the subset of data containing router B (excluding router A), we decided to attempt to improve the knn analysis by running a weighted knn analysis. This yielded interesting results: during cross validation with the perfect grid of data supplied in the `offline` dataset, it performed significantly worse than the other models, however when used with the messy `online` dataset (where locations were not perfectly placed throughout the grid, see the figure in the introduction), it performed very well. We believe this is due to the weighting effect, which makes it much less likely for a position to be predicted to be a whole number. The offline data has observations carefully selected to make a grid, spaced 1 meter apart, while the online dataset does not. By dividing the elements of the average by a fraction, it is much less likely to end in a whole number, meaning the errors should build up very quickly in the offline data, while with the online data, this is less likely, as we do not have integer points. However, this is just a hypothesis, and deserves more practical testing. Therefore, we advise to use the standar knn algorithm using the subset of data containing Router B. This performed consistently well through all cross validation and online testing.

# Appendix

To view any code, please unfold the code throughout this document. For the leader's convenience, it is provided both where it was used and in full at the bottom. It is advised to read the code where it was used, as it is rather complex and nested.


```r
labs = knitr::all_labels()
labs = labs[!labs %in% c("setup", "toc", "getlabels", "allcode")]
```


```r
knitr::include_graphics("CleverZonkedElk.png")
pander::pander(list(t = "Time stamp (Milliseconds) since 12:00am, January 1, 1970", 
    Id = "router MAC address", Pos = "Router location", Degree = "Direction scanning device was carried by the researcher, measured in Degrees", 
    MAC = "MAC address of either the accessrouter, or scanning device combined with corresponding values for signal strength (dBm), the mode in which it was operating(adhoc scanner = 1, access router = 3), and its corresponding channel frequency.", 
    Signal = "Received Signal Strength in DbM"))
knitr::read_chunk("utils.R")
knitr::read_chunk("analysis_plots.R")
knitr::read_chunk("excl_b.R")
# first we define the processline function, which unsurprisingly processes a
# single line of the offline or online.txt
library(tidyverse)
processLine = function(x) {
    # here we split the line at the weird markers. Strsplit returns a list we
    # take the first item of the list
    tokens = strsplit(x, "[;=,]")[[1]]
    if (length(tokens) == 10) {
        return(NULL)
    }
    # now we are going to stack the tokens
    tmp = matrix(tokens[-(1:10)], , 4, byrow = TRUE)
    cbind(matrix(tokens[c(2, 4, 6:8, 10)], nrow(tmp), 6, byrow = TRUE), tmp)
}
roundOrientation = function(angles) {
    refs = seq(0, by = 45, length = 9)
    q = sapply(angles, function(o) which.min(abs(o - refs)))
    c(refs[1:8], 0)[q]
}
# this reads in the data
readData <- function(filename, subMacs = c("00:0f:a3:39:e1:c0", "00:0f:a3:39:dd:cd", 
    "00:14:bf:b1:97:8a", "00:14:bf:3b:c7:c6", "00:14:bf:b1:97:90", "00:14:bf:b1:97:8d", 
    "00:14:bf:b1:97:81")) {
    # read it in line by line
    txt = readLines(filename)
    # ignore comments
    lines = txt[substr(txt, 1, 1) != "#"]
    # process (tokenize and stack) each line
    tmp = lapply(lines, processLine)
    # rbind each elemnt of the list together
    offline = as.data.frame(do.call(rbind, tmp), stringsAsFactors = FALSE)
    # set the names of our matrix
    names(offline) = c("time", "scanMac", "posX", "posY", "posZ", "orientation", 
        "mac", "signal", "channel", "type")
    
    # keep only signals from access points
    offline = offline[offline$type == "3", ]
    
    # drop scanMac, posZ, channel, and type - no info in them
    dropVars = c("scanMac", "posZ", "channel", "type")
    offline = offline[, !(names(offline) %in% dropVars)]
    
    # drop more unwanted access points
    offline = offline[offline$mac %in% subMacs, ]
    
    # convert numeric values
    numVars = c("time", "posX", "posY", "orientation", "signal")
    offline[numVars] = lapply(offline[numVars], as.numeric)
    
    # convert time to POSIX
    offline$rawTime = offline$time
    offline$time = offline$time/1000
    class(offline$time) = c("POSIXt", "POSIXct")
    
    # round orientations to nearest 45
    offline$angle = roundOrientation(offline$orientation)
    
    return(offline)
}
offline <- readData("offline.final.trace.txt")
offline
offline <- readData("offline.final.trace.txt")
# fix up the xypos
offline$posXY <- paste(offline$posX, offline$posY, sep = "-")
byLocAngleAP = with(offline, by(offline, list(posXY, angle, mac), function(x) x))

signalSummary = lapply(byLocAngleAP, function(oneLoc) {
    ans = oneLoc[1, ]
    ans$medSignal = median(oneLoc$signal)
    ans$avgSignal = mean(oneLoc$signal)
    ans$num = length(oneLoc$signal)
    ans$sdSignal = sd(oneLoc$signal)
    ans$iqrSignal = IQR(oneLoc$signal)
    ans
})
offlineSummary_original = do.call("rbind", signalSummary)
offlineSummary <- offlineSummary_original %>% filter(mac != router_b)

online <- readData("online.final.trace.txt", subMacs = unique(offlineSummary$mac))
online$posXY <- paste(online$posX, online$posY, sep = "-")

keepVars = c("posXY", "posX", "posY", "orientation", "angle")
byLoc = with(online, by(online, list(posXY), function(x) {
    ans = x[1, keepVars]
    avgSS = tapply(x$signal, x$mac, mean)
    y = matrix(avgSS, nrow = 1, ncol = 6, dimnames = list(ans$posXY, names(avgSS)))
    cbind(ans, y)
}))

onlineSummary = do.call("rbind", byLoc)
calcError <- function(estXY, actualXY) sum(rowSums((estXY - actualXY)^2))

reshapeSS1 <- function(data, varSignal = "signal", keepVars = c("posXY", "posX", 
    "posY")) {
    byLocation <- with(data, by(data, list(posXY), function(x) {
        ans <- x[1, keepVars]
        avgSS <- tapply(x[, varSignal], x$mac, mean)
        y <- matrix(avgSS, nrow = 1, ncol = 6, dimnames = list(ans$posXY, names(avgSS)))
        cbind(ans, y)
    }))
    
    newDataSS <- do.call("rbind", byLocation)
    return(newDataSS)
}


selectTrain1 <- function(angleNewObs, signals = NULL, m = 1) {
    # m is the number of angles to keep between 1 and 5
    refs <- seq(0, by = 45, length = 8)
    nearestAngle <- roundOrientation(angleNewObs)
    
    if (m%%2 == 1) 
        angles <- seq(-45 * (m - 1)/2, 45 * (m - 1)/2, length = m) else {
        m = m + 1
        angles <- seq(-45 * (m - 1)/2, 45 * (m - 1)/2, length = m)
        if (sign(angleNewObs - nearestAngle) > -1) 
            angles <- angles[-1] else angles <- angles[-m]
    }
    # round angles
    angles <- angles + nearestAngle
    angles[angles < 0] <- angles[angles < 0] + 360
    angles[angles > 360] <- angles[angles > 360] - 360
    angles <- sort(angles)
    
    offlineSubset <- signals[signals$angle %in% angles, ]
    reshapeSS1(offlineSubset, varSignal = "avgSignal")
}


findNN1 <- function(newSignal, trainSubset) {
    diffs <- apply(trainSubset[, 4:9], 1, function(x) x - newSignal)
    dists <- apply(diffs, 2, function(x) sqrt(sum(x^2)))
    closest <- order(dists)
    weightDF <- trainSubset[closest, 1:3]
    weightDF$weight <- 1/closest
    return(weightDF)
}


predXY1 <- function(newSignals, newAngles, trainData, numAngles = 1, k = 3) {
    closeXY <- list(length = nrow(newSignals))
    
    for (i in 1:nrow(newSignals)) {
        trainSS <- selectTrain1(newAngles[i], trainData, m = numAngles)
        closeXY[[i]] <- findNN1(newSignal = as.numeric(newSignals[i, ]), trainSS)
    }
    
    estXY <- lapply(closeXY, function(x) sapply(x[, 2:3], function(x) mean(x[1:k])))
    estXY <- do.call("rbind", estXY)
    return(estXY)
}


v = 11
permuteLocs = sample(unique(offlineSummary$posXY))
permuteLocs = matrix(permuteLocs, ncol = v, nrow = floor(length(permuteLocs)/v))

onlineFold = subset(offlineSummary, posXY %in% permuteLocs[, 1])
reshapeSS1 = function(data, varSignal = "signal", keepVars = c("posXY", "posX", 
    "posY"), sampleAngle = FALSE, refs = seq(0, 315, by = 45)) {
    byLocation = with(data, by(data, list(posXY), function(x) {
        if (sampleAngle) {
            x = x[x$angle == sample(refs, size = 1), ]
        }
        ans = x[1, keepVars]
        avgSS = tapply(x[, varSignal], x$mac, mean)
        y = matrix(avgSS, nrow = 1, ncol = 6, dimnames = list(ans$posXY, names(avgSS)))
        cbind(ans, y)
    }))
    
    newDataSS = do.call("rbind", byLocation)
    return(newDataSS)
}


offline = offline[offline$mac != "00:0f:a3:39:dd:cd", ]

keepVars = c("posXY", "posX", "posY", "orientation", "angle")

onlineCVSummary = reshapeSS1(offline, keepVars = keepVars, sampleAngle = TRUE)

onlineFold = subset(onlineCVSummary, posXY %in% permuteLocs[, 1])

offlineFold = subset(offlineSummary, posXY %in% permuteLocs[, -1])

estFold = predXY1(newSignals = onlineFold[, 6:11], newAngles = onlineFold[, 
    4], offlineFold, numAngles = 1, k = 3)

actualFold = onlineFold[, c("posX", "posY")]

NNeighbors = 20
K = NNeighbors
err = numeric(K)

for (j in 1:v) {
    onlineFold = subset(onlineCVSummary, posXY %in% permuteLocs[, j])
    offlineFold = subset(offlineSummary, posXY %in% permuteLocs[, -j])
    actualFold = onlineFold[, c("posX", "posY")]
    
    for (k in 1:K) {
        estFold = predXY1(newSignals = onlineFold[, 6:11], newAngles = onlineFold[, 
            4], offlineFold, numAngles = 1, k = k)
        err[k] = err[k] + calcError(estFold, actualFold)
    }
}

errdf <- data.frame(router_a = err)
plot(y = err, x = (1:K), type = "l", lwd = 2, ylim = c(800, 2100), xlab = "Number of Neighbors", 
    ylab = "Sum of Square Errors", main = "Error vs K, with Router A Data")

rmseMin = min(err)
kMin = which(err == rmseMin)[1]
segments(x0 = 0, x1 = kMin, y0 = rmseMin, col = gray(0.4), lty = 2, lwd = 2)
segments(x0 = kMin, x1 = kMin, y0 = 1100, y1 = rmseMin, col = grey(0.4), lty = 2, 
    lwd = 2)

# mtext(kMin, side = 1, line = 1, at = kMin, col = grey(0.4))
text(x = kMin - 2, y = rmseMin + 40, label = as.character(round(rmseMin)), col = grey(0.4))


estXYkmin1 = predXY1(newSignals = onlineSummary[, 6:11], newAngles = onlineSummary[, 
    4], offlineSummary, numAngles = 1, k = kMin)
actualXY = onlineSummary[, c("posX", "posY")]
err_cv1 <- calcError(estXYkmin1, actualXY)
trainPoints = offlineSummary[offlineSummary$angle == 0 & offlineSummary$mac == 
    "00:0f:a3:39:e1:c0", c("posX", "posY")]


floorErrorMap = function(estXY, actualXY, trainPoints = NULL, AP = NULL) {
    
    plot(0, 0, xlim = c(0, 35), ylim = c(-3, 15), type = "n", xlab = "", ylab = "", 
        axes = FALSE, main = "Floor Map of Predictions", sub = "■ = Access Point, ● = Actual, ✷ = Predicted")
    box()
    if (!is.null(AP)) 
        points(AP, pch = 15)
    if (!is.null(trainPoints)) 
        points(trainPoints, pch = 19, col = "grey", cex = 0.6)
    
    points(x = actualXY[, 1], y = actualXY[, 2], pch = 19, cex = 0.8)
    points(x = estXY[, 1], y = estXY[, 2], pch = 8, cex = 0.8)
    segments(x0 = estXY[, 1], y0 = estXY[, 2], x1 = actualXY[, 1], y1 = actualXY[, 
        2], lwd = 2, col = "red")
}


actualXY = onlineSummary[, c("posX", "posY")]
offline <- readData("offline.final.trace.txt")
# fix up the xypos
offline$posXY <- paste(offline$posX, offline$posY, sep = "-")
byLocAngleAP = with(offline, by(offline, list(posXY, angle, mac), function(x) x))

signalSummary = lapply(byLocAngleAP, function(oneLoc) {
    ans = oneLoc[1, ]
    ans$medSignal = median(oneLoc$signal)
    ans$avgSignal = mean(oneLoc$signal)
    ans$num = length(oneLoc$signal)
    ans$sdSignal = sd(oneLoc$signal)
    ans$iqrSignal = IQR(oneLoc$signal)
    ans
})
offlineSummary_original = do.call("rbind", signalSummary)
offlineSummary <- offlineSummary_original %>% filter(mac != router_a)

online <- readData("online.final.trace.txt", subMacs = unique(offlineSummary$mac))
online$posXY <- paste(online$posX, online$posY, sep = "-")

keepVars = c("posXY", "posX", "posY", "orientation", "angle")
byLoc = with(online, by(online, list(posXY), function(x) {
    ans = x[1, keepVars]
    avgSS = tapply(x$signal, x$mac, mean)
    y = matrix(avgSS, nrow = 1, ncol = 6, dimnames = list(ans$posXY, names(avgSS)))
    cbind(ans, y)
}))

onlineSummary = do.call("rbind", byLoc)


v = 11
permuteLocs = sample(unique(offlineSummary$posXY))
permuteLocs = matrix(permuteLocs, ncol = v, nrow = floor(length(permuteLocs)/v))

onlineFold = subset(offlineSummary, posXY %in% permuteLocs[, 1])


offline = offline[offline$mac != router_a, ]

keepVars = c("posXY", "posX", "posY", "orientation", "angle")

onlineCVSummary = reshapeSS1(offline, keepVars = keepVars, sampleAngle = TRUE)

onlineFold = subset(onlineCVSummary, posXY %in% permuteLocs[, 1])

offlineFold = subset(offlineSummary, posXY %in% permuteLocs[, -1])

estFold = predXY1(newSignals = onlineFold[, 6:11], newAngles = onlineFold[, 
    4], offlineFold, numAngles = 1, k = 3)

actualFold = onlineFold[, c("posX", "posY")]

NNeighbors = 20
K = NNeighbors
err = numeric(K)

for (j in 1:v) {
    onlineFold = subset(onlineCVSummary, posXY %in% permuteLocs[, j])
    offlineFold = subset(offlineSummary, posXY %in% permuteLocs[, -j])
    actualFold = onlineFold[, c("posX", "posY")]
    
    for (k in 1:K) {
        estFold = predXY1(newSignals = onlineFold[, 6:11], newAngles = onlineFold[, 
            4], offlineFold, numAngles = 1, k = k)
        err[k] = err[k] + calcError(estFold, actualFold)
    }
}

errdf$router_b <- err
plot(y = err, x = (1:K), type = "l", lwd = 2, ylim = c(800, 2100), xlab = "Number of Neighbors", 
    ylab = "Sum of Square Errors", main = "Error vs K, with Router B Data")

rmseMin = min(err)
kMin = which(err == rmseMin)[1]
segments(x0 = 0, x1 = kMin, y0 = rmseMin, col = gray(0.4), lty = 2, lwd = 2)
segments(x0 = kMin, x1 = kMin, y0 = 1100, y1 = rmseMin, col = grey(0.4), lty = 2, 
    lwd = 2)

# mtext(kMin, side = 1, line = 1, at = kMin, col = grey(0.4))
text(x = kMin - 2, y = rmseMin + 40, label = as.character(round(rmseMin)), col = grey(0.4))


estXYkmin2 = predXY1(newSignals = onlineSummary[, 6:11], newAngles = onlineSummary[, 
    4], offlineSummary, numAngles = 1, k = kMin)


actualXY = onlineSummary[, c("posX", "posY")]
err_cv2 <- calcError(estXYkmin2, actualXY)

trainPoints = offlineSummary[offlineSummary$angle == 0 & offlineSummary$mac == 
    "00:0f:a3:39:e1:c0", c("posX", "posY")]


floorErrorMap = function(estXY, actualXY, trainPoints = NULL, AP = NULL) {
    
    plot(0, 0, xlim = c(0, 35), ylim = c(-3, 15), type = "n", xlab = "", ylab = "", 
        axes = FALSE, main = "Floor Map of Predictions", sub = "■ = Access Point, ● = Actual, ✷ = Predicted")
    box()
    if (!is.null(AP)) 
        points(AP, pch = 15)
    if (!is.null(trainPoints)) 
        points(trainPoints, pch = 19, col = "grey", cex = 0.6)
    
    points(x = actualXY[, 1], y = actualXY[, 2], pch = 19, cex = 0.8)
    points(x = estXY[, 1], y = estXY[, 2], pch = 8, cex = 0.8)
    segments(x0 = estXY[, 1], y0 = estXY[, 2], x1 = actualXY[, 1], y1 = actualXY[, 
        2], lwd = 2, col = "red")
}

actualXY = onlineSummary[, c("posX", "posY")]
errdf$k <- 1:nrow(errdf)
errdf %>% gather_("Router", "RMSE", names(errdf)[-length(errdf)]) %>% ggplot() + 
    geom_line(aes(x = k, y = RMSE, color = Router)) + plt_theme + ggtitle("RMSE Over K by Router Subset")
data.frame(router = c("router a", "router b"), `online Sum of Square errors` = c(err_cv1, 
    err_cv2))
offline <- readData("offline.final.trace.txt")
# fix up the xypos
offline$posXY <- paste(offline$posX, offline$posY, sep = "-")
byLocAngleAP = with(offline, by(offline, list(posXY, angle, mac), function(x) x))

signalSummary = lapply(byLocAngleAP, function(oneLoc) {
    ans = oneLoc[1, ]
    ans$medSignal = median(oneLoc$signal)
    ans$avgSignal = mean(oneLoc$signal)
    ans$num = length(oneLoc$signal)
    ans$sdSignal = sd(oneLoc$signal)
    ans$iqrSignal = IQR(oneLoc$signal)
    ans
})
offlineSummary = do.call("rbind", signalSummary)

online <- readData("online.final.trace.txt", subMacs = unique(offlineSummary$mac))
online$posXY <- paste(online$posX, online$posY, sep = "-")

keepVars = c("posXY", "posX", "posY", "orientation", "angle")
byLoc = with(online, by(online, list(posXY), function(x) {
    ans = x[1, keepVars]
    avgSS = tapply(x$signal, x$mac, mean)
    y = matrix(avgSS, nrow = 1, ncol = 7, dimnames = list(ans$posXY, names(avgSS)))
    cbind(ans, y)
}))

onlineSummary = do.call("rbind", byLoc)
calcError <- function(estXY, actualXY) sum(rowSums((estXY - actualXY)^2))

reshapeSS2 <- function(data, varSignal = "signal", keepVars = c("posXY", "posX", 
    "posY")) {
    byLocation <- with(data, by(data, list(posXY), function(x) {
        ans <- x[1, keepVars]
        avgSS <- tapply(x[, varSignal], x$mac, mean)
        y <- matrix(avgSS, nrow = 1, ncol = 7, dimnames = list(ans$posXY, names(avgSS)))
        cbind(ans, y)
    }))
    
    newDataSS <- do.call("rbind", byLocation)
    return(newDataSS)
}


selectTrain2 <- function(angleNewObs, signals = NULL, m = 1) {
    # m is the number of angles to keep between 1 and 5
    refs <- seq(0, by = 45, length = 8)
    nearestAngle <- roundOrientation(angleNewObs)
    
    if (m%%2 == 1) 
        angles <- seq(-45 * (m - 1)/2, 45 * (m - 1)/2, length = m) else {
        m = m + 1
        angles <- seq(-45 * (m - 1)/2, 45 * (m - 1)/2, length = m)
        if (sign(angleNewObs - nearestAngle) > -1) 
            angles <- angles[-1] else angles <- angles[-m]
    }
    # round angles
    angles <- angles + nearestAngle
    angles[angles < 0] <- angles[angles < 0] + 360
    angles[angles > 360] <- angles[angles > 360] - 360
    angles <- sort(angles)
    
    offlineSubset <- signals[signals$angle %in% angles, ]
    reshapeSS2(offlineSubset, varSignal = "avgSignal")
}


findNN2 <- function(newSignal, trainSubset) {
    diffs <- apply(trainSubset[, 4:9], 1, function(x) x - newSignal)
    dists <- apply(diffs, 2, function(x) sqrt(sum(x^2)))
    closest <- order(dists)
    weightDF <- trainSubset[closest, 1:3]
    weightDF$weight <- 1/closest
    return(weightDF)
}


predXY2 <- function(newSignals, newAngles, trainData, numAngles = 1, k = 3) {
    closeXY <- list(length = nrow(newSignals))
    
    for (i in 1:nrow(newSignals)) {
        trainSS <- selectTrain2(newAngles[i], trainData, m = numAngles)
        closeXY[[i]] <- findNN2(newSignal = as.numeric(newSignals[i, ]), trainSS)
    }
    
    estXY <- lapply(closeXY, function(x) sapply(x[, 2:3], function(x) mean(x[1:k])))
    estXY <- do.call("rbind", estXY)
    return(estXY)
}


v = 11
permuteLocs = sample(unique(offlineSummary$posXY))
permuteLocs = matrix(permuteLocs, ncol = v, nrow = floor(length(permuteLocs)/v))

onlineFold = subset(offlineSummary, posXY %in% permuteLocs[, 1])
reshapeSS2 = function(data, varSignal = "signal", keepVars = c("posXY", "posX", 
    "posY"), sampleAngle = FALSE, refs = seq(0, 315, by = 45)) {
    byLocation = with(data, by(data, list(posXY), function(x) {
        if (sampleAngle) {
            x = x[x$angle == sample(refs, size = 1), ]
        }
        ans = x[1, keepVars]
        avgSS = tapply(x[, varSignal], x$mac, mean)
        y = matrix(avgSS, nrow = 1, ncol = 7, dimnames = list(ans$posXY, names(avgSS)))
        cbind(ans, y)
    }))
    
    newDataSS = do.call("rbind", byLocation)
    return(newDataSS)
}


keepVars = c("posXY", "posX", "posY", "orientation", "angle")

onlineCVSummary = reshapeSS2(offline, keepVars = keepVars, sampleAngle = TRUE)

onlineFold = subset(onlineCVSummary, posXY %in% permuteLocs[, 1])

offlineFold = subset(offlineSummary, posXY %in% permuteLocs[, -1])

estFold = predXY2(newSignals = onlineFold[, 6:12], newAngles = onlineFold[, 
    5], offlineFold, numAngles = 1, k = 3)

actualFold = onlineFold[, c("posX", "posY")]

NNeighbors = 20
K = NNeighbors
err = numeric(K)

for (j in 1:v) {
    onlineFold = subset(onlineCVSummary, posXY %in% permuteLocs[, j])
    offlineFold = subset(offlineSummary, posXY %in% permuteLocs[, -j])
    actualFold = onlineFold[, c("posX", "posY")]
    
    for (k in 1:K) {
        estFold = predXY2(newSignals = onlineFold[, 6:11], newAngles = onlineFold[, 
            4], offlineFold, numAngles = 1, k = k)
        err[k] = err[k] + calcError(estFold, actualFold)
    }
}

errdf$both <- err
plot(y = err, x = (1:K), type = "l", lwd = 2, ylim = c(800, 2100), xlab = "Number of Neighbors", 
    ylab = "Sum of Square Errors", main = "Error vs K, with all Data")

rmseMin = min(err)
kMin = which(err == rmseMin)[1]
segments(x0 = 0, x1 = kMin, y0 = rmseMin, col = gray(0.4), lty = 2, lwd = 2)
segments(x0 = kMin, x1 = kMin, y0 = 1100, y1 = rmseMin, col = grey(0.4), lty = 2, 
    lwd = 2)

# mtext(kMin, side = 1, line = 1, at = kMin, col = grey(0.4))
text(x = kMin - 2, y = rmseMin + 40, label = as.character(round(rmseMin)), col = grey(0.4))


estXYkmin3 = predXY2(newSignals = onlineSummary[, 6:12], newAngles = onlineSummary[, 
    5], offlineSummary, numAngles = 1, k = kMin)
actualXY = onlineSummary[, c("posX", "posY")]
err_cv3 <- calcError(estXYkmin3, actualXY)

trainPoints = offlineSummary[offlineSummary$angle == 0 & offlineSummary$mac == 
    "00:0f:a3:39:e1:c0", c("posX", "posY")]


floorErrorMap = function(estXY, actualXY, trainPoints = NULL, AP = NULL) {
    
    plot(0, 0, xlim = c(0, 35), ylim = c(-3, 15), type = "n", xlab = "", ylab = "", 
        axes = FALSE, main = "Floor Map of Predictions", sub = "■ = Access Point, ● = Actual, ✷ = Predicted")
    box()
    if (!is.null(AP)) 
        points(AP, pch = 15)
    if (!is.null(trainPoints)) 
        points(trainPoints, pch = 19, col = "grey", cex = 0.6)
    
    points(x = actualXY[, 1], y = actualXY[, 2], pch = 19, cex = 0.8)
    points(x = estXY[, 1], y = estXY[, 2], pch = 8, cex = 0.8)
    segments(x0 = estXY[, 1], y0 = estXY[, 2], x1 = actualXY[, 1], y1 = actualXY[, 
        2], lwd = 2, col = "red")
}


actualXY = onlineSummary[, c("posX", "posY")]
errdf %>% gather_("Router", "RMSE", names(errdf)[-(length(errdf) - 1)]) %>% 
    ggplot() + geom_line(aes(x = k, y = RMSE, color = Router)) + plt_theme + 
    ggtitle("RMSE Over K by Router Subset")

data.frame(router = c("router a", "router b", "both"), `Online sum of squares` = c(err_cv1, 
    err_cv2, err_cv3))
offline <- readData("offline.final.trace.txt")
# fix up the xypos
offline$posXY <- paste(offline$posX, offline$posY, sep = "-")
byLocAngleAP = with(offline, by(offline, list(posXY, angle, mac), function(x) x))

signalSummary = lapply(byLocAngleAP, function(oneLoc) {
    ans = oneLoc[1, ]
    ans$medSignal = median(oneLoc$signal)
    ans$avgSignal = mean(oneLoc$signal)
    ans$num = length(oneLoc$signal)
    ans$sdSignal = sd(oneLoc$signal)
    ans$iqrSignal = IQR(oneLoc$signal)
    ans
})
offlineSummary_original = do.call("rbind", signalSummary)
offlineSummary <- offlineSummary_original %>% filter(mac != router_a)

online <- readData("online.final.trace.txt", subMacs = unique(offlineSummary$mac))
online$posXY <- paste(online$posX, online$posY, sep = "-")

keepVars = c("posXY", "posX", "posY", "orientation", "angle")
byLoc = with(online, by(online, list(posXY), function(x) {
    ans = x[1, keepVars]
    avgSS = tapply(x$signal, x$mac, mean)
    y = matrix(avgSS, nrow = 1, ncol = 6, dimnames = list(ans$posXY, names(avgSS)))
    cbind(ans, y)
}))

onlineSummary = do.call("rbind", byLoc)
calcError <- function(estXY, actualXY) sum(rowSums((estXY - actualXY)^2))

reshapeSS1 <- function(data, varSignal = "signal", keepVars = c("posXY", "posX", 
    "posY")) {
    byLocation <- with(data, by(data, list(posXY), function(x) {
        ans <- x[1, keepVars]
        avgSS <- tapply(x[, varSignal], x$mac, mean)
        y <- matrix(avgSS, nrow = 1, ncol = 6, dimnames = list(ans$posXY, names(avgSS)))
        cbind(ans, y)
    }))
    
    newDataSS <- do.call("rbind", byLocation)
    return(newDataSS)
}


selectTrain1 <- function(angleNewObs, signals = NULL, m = 1) {
    # m is the number of angles to keep between 1 and 5
    refs <- seq(0, by = 45, length = 8)
    nearestAngle <- roundOrientation(angleNewObs)
    
    if (m%%2 == 1) 
        angles <- seq(-45 * (m - 1)/2, 45 * (m - 1)/2, length = m) else {
        m = m + 1
        angles <- seq(-45 * (m - 1)/2, 45 * (m - 1)/2, length = m)
        if (sign(angleNewObs - nearestAngle) > -1) 
            angles <- angles[-1] else angles <- angles[-m]
    }
    # round angles
    angles <- angles + nearestAngle
    angles[angles < 0] <- angles[angles < 0] + 360
    angles[angles > 360] <- angles[angles > 360] - 360
    angles <- sort(angles)
    
    offlineSubset <- signals[signals$angle %in% angles, ]
    reshapeSS1(offlineSubset, varSignal = "avgSignal")
}


findNN_weighted = function(newSignal, trainSubset) {
    diffs = apply(trainSubset[, 4:9], 1, function(x) x - newSignal)
    dists <- sqrt(colSums(diffs^2))  # why is the book using apply when R is vectorized?
    weighted_dists <- (1/dists)/(sum(1/dists))
    closest = order(dists)
    return(list(trainSubset[closest, 1:3], (1/dists)[order(weighted_dists, decreasing = TRUE)]))
}


library(foreach)
library(doParallel)
cl <- makeCluster(parallel::detectCores() - 1)
registerDoParallel(cl)
predXY_weighted = function(newSignals, newAngles, trainData, numAngles = 1, 
    k = 3) {
    l <- nrow(newSignals)
    res <- foreach(i = 1:nrow(newSignals)) %do% {
        trainSS <- selectTrain1(newAngles[i], trainData, m = numAngles)
        nn <- findNN_weighted(newSignal = as.numeric(newSignals[i, ]), trainSS)[[1]]
        wdist <- findNN_weighted(newSignal = as.numeric(newSignals[i, ]), trainSS)[[2]]
        weighted_dist <- wdist[1:k]/sum(wdist[1:k])
        lab <- as.matrix(nn[1:k, 2:3] * weighted_dist)
        return(lab)
    }
    estXY = lapply(res, colSums)
    estXY = do.call("rbind", estXY)
    return(estXY)
}

v = 11
permuteLocs = sample(unique(offlineSummary$posXY))
permuteLocs = matrix(permuteLocs, ncol = v, nrow = floor(length(permuteLocs)/v))

onlineFold = subset(offlineSummary, posXY %in% permuteLocs[, 1])
reshapeSS1 = function(data, varSignal = "signal", keepVars = c("posXY", "posX", 
    "posY"), sampleAngle = FALSE, refs = seq(0, 315, by = 45)) {
    byLocation = with(data, by(data, list(posXY), function(x) {
        if (sampleAngle) {
            x = x[x$angle == sample(refs, size = 1), ]
        }
        ans = x[1, keepVars]
        avgSS = tapply(x[, varSignal], x$mac, mean)
        y = matrix(avgSS, nrow = 1, ncol = 6, dimnames = list(ans$posXY, names(avgSS)))
        cbind(ans, y)
    }))
    
    newDataSS = do.call("rbind", byLocation)
    return(newDataSS)
}


offline = offline[offline$mac != "00:0f:a3:39:dd:cd", ]

keepVars = c("posXY", "posX", "posY", "orientation", "angle")

onlineCVSummary = reshapeSS1(offline, keepVars = keepVars, sampleAngle = TRUE)

onlineFold = subset(onlineCVSummary, posXY %in% permuteLocs[, 1])

offlineFold = subset(offlineSummary, posXY %in% permuteLocs[, -1])

estFold = predXY_weighted(newSignals = onlineFold[, 6:11], newAngles = onlineFold[, 
    4], offlineFold, numAngles = 1, k = 3)


actualFold = onlineFold[, c("posX", "posY")]

NNeighbors = 20
K = NNeighbors
err = numeric(K)

for (j in 1:v) {
    onlineFold = subset(onlineCVSummary, posXY %in% permuteLocs[, j])
    offlineFold = subset(offlineSummary, posXY %in% permuteLocs[, -j])
    actualFold = onlineFold[, c("posX", "posY")]
    
    for (k in 1:K) {
        estFold = predXY_weighted(newSignals = onlineFold[, 6:11], newAngles = onlineFold[, 
            4], offlineFold, numAngles = 1, k = k)
        err[k] = err[k] + calcError(estFold, actualFold)
    }
}

errdf$weighted <- err
plot(y = err, x = (1:K), type = "l", lwd = 2, ylim = c(800, 8000), xlab = "Number of Neighbors", 
    ylab = "Sum of Square Errors", main = "Error vs K, with weighted Data")

rmseMin = min(err)
kMin = which(err == rmseMin)[1]
segments(x0 = 0, x1 = kMin, y0 = rmseMin, col = gray(0.4), lty = 2, lwd = 2)
segments(x0 = kMin, x1 = kMin, y0 = 1100, y1 = rmseMin, col = grey(0.4), lty = 2, 
    lwd = 2)

# mtext(kMin, side = 1, line = 1, at = kMin, col = grey(0.4))
text(x = kMin - 2, y = rmseMin + 40, label = as.character(round(rmseMin)), col = grey(0.4))


estXYkmin4 = predXY_weighted(newSignals = onlineSummary[, 6:11], newAngles = onlineSummary[, 
    4], offlineSummary, numAngles = 1, k = kMin)
actualXY = onlineSummary[, c("posX", "posY")]
err_cv4 <- calcError(estXYkmin4, actualXY)

trainPoints = offlineSummary[offlineSummary$angle == 0 & offlineSummary$mac == 
    "00:0f:a3:39:e1:c0", c("posX", "posY")]


floorErrorMap = function(estXY, actualXY, trainPoints = NULL, AP = NULL) {
    
    plot(0, 0, xlim = c(0, 35), ylim = c(-3, 15), type = "n", xlab = "", ylab = "", 
        axes = FALSE, main = "Floor Map of Predictions", sub = "■ = Access Point, ● = Actual, ✷ = Predicted")
    box()
    if (!is.null(AP)) 
        points(AP, pch = 15)
    if (!is.null(trainPoints)) 
        points(trainPoints, pch = 19, col = "grey", cex = 0.6)
    
    points(x = actualXY[, 1], y = actualXY[, 2], pch = 19, cex = 0.8)
    points(x = estXY[, 1], y = estXY[, 2], pch = 8, cex = 0.8)
    segments(x0 = estXY[, 1], y0 = estXY[, 2], x1 = actualXY[, 1], y1 = actualXY[, 
        2], lwd = 2, col = "red")
}
actualXY = onlineSummary[, c("posX", "posY")]
errdf %>% gather_("Router", "RMSE", names(errdf)[-(length(errdf) - 2)]) %>% 
    ggplot() + geom_line(aes(x = k, y = RMSE, color = Router)) + plt_theme + 
    ggtitle("RMSE Over K by Router Subset")
data.frame(router = c("router a", "router b", "both", "weighted"), `Online sum of squares` = c(err_cv1, 
    err_cv2, err_cv3, err_cv4))
# first we define the processline function, which unsurprisingly processes a
# single line of the offline or online.txt
library(tidyverse)
processLine = function(x) {
    # here we split the line at the weird markers. Strsplit returns a list we
    # take the first item of the list
    tokens = strsplit(x, "[;=,]")[[1]]
    if (length(tokens) == 10) {
        return(NULL)
    }
    # now we are going to stack the tokens
    tmp = matrix(tokens[-(1:10)], , 4, byrow = TRUE)
    cbind(matrix(tokens[c(2, 4, 6:8, 10)], nrow(tmp), 6, byrow = TRUE), tmp)
}
roundOrientation = function(angles) {
    refs = seq(0, by = 45, length = 9)
    q = sapply(angles, function(o) which.min(abs(o - refs)))
    c(refs[1:8], 0)[q]
}
# this reads in the data
readData <- function(filename, subMacs = c("00:0f:a3:39:e1:c0", "00:0f:a3:39:dd:cd", 
    "00:14:bf:b1:97:8a", "00:14:bf:3b:c7:c6", "00:14:bf:b1:97:90", "00:14:bf:b1:97:8d", 
    "00:14:bf:b1:97:81")) {
    # read it in line by line
    txt = readLines(filename)
    # ignore comments
    lines = txt[substr(txt, 1, 1) != "#"]
    # process (tokenize and stack) each line
    tmp = lapply(lines, processLine)
    # rbind each elemnt of the list together
    offline = as.data.frame(do.call(rbind, tmp), stringsAsFactors = FALSE)
    # set the names of our matrix
    names(offline) = c("time", "scanMac", "posX", "posY", "posZ", "orientation", 
        "mac", "signal", "channel", "type")
    
    # keep only signals from access points
    offline = offline[offline$type == "3", ]
    
    # drop scanMac, posZ, channel, and type - no info in them
    dropVars = c("scanMac", "posZ", "channel", "type")
    offline = offline[, !(names(offline) %in% dropVars)]
    
    # drop more unwanted access points
    offline = offline[offline$mac %in% subMacs, ]
    
    # convert numeric values
    numVars = c("time", "posX", "posY", "orientation", "signal")
    offline[numVars] = lapply(offline[numVars], as.numeric)
    
    # convert time to POSIX
    offline$rawTime = offline$time
    offline$time = offline$time/1000
    class(offline$time) = c("POSIXt", "POSIXct")
    
    # round orientations to nearest 45
    offline$angle = roundOrientation(offline$orientation)
    
    return(offline)
}
offline <- readData("offline.final.trace.txt")
router_b <- "00:0f:a3:39:dd:cd"
router_a <- "00:0f:a3:39:e1:c0"
fixfonts <- theme(text = element_text(family = "serif", , face = "bold"))
plt_theme <- ggthemes::theme_hc() + fixfonts
offline %>% mutate(angle = factor(angle)) %>% filter(posX == 2 & posY == 12) %>% 
    ggplot + geom_boxplot(aes(y = signal, x = angle)) + facet_wrap(. ~ mac, 
    ncol = 2) + ggtitle("Boxplot of Signal vs Angle at All MAC Addresses") + 
    plt_theme
offline %>% mutate(angle = factor(angle)) %>% filter(posX == 2 & posY == 12 & 
    mac %in% c(router_a, router_b)) %>% ggplot() + geom_boxplot(aes(y = signal, 
    x = angle)) + facet_wrap(. ~ mac, ncol = 1) + ggtitle("Signal vs Angle for a fixed position at selected MACS") + 
    plt_theme
offline %>% mutate(angle = factor(angle)) %>% group_by(mac) %>% summarise(signal_avg = mean(signal), 
    signal_std = sd(signal))
offline %>% mutate(angle = factor(angle)) %>% filter(posX == 2 & posY == 12) %>% 
    ggplot(aes(signal, fill = angle)) + geom_density() + facet_wrap(. ~ mac, 
    ncol = 1) + ggtitle("Per Angle Signal Density at the Two MACS") + plt_theme + 
    scale_fill_viridis_d()
offline %>% mutate(angle = factor(angle)) %>% filter(posX == 2 & posY == 12 & 
    mac %in% c(router_a, router_b)) %>% ggplot(aes(signal, fill = angle)) + 
    geom_density() + facet_wrap(. ~ mac, ncol = 1) + ggtitle("Per Angle Signal Density at the Two MACS") + 
    plt_theme + scale_fill_viridis_d()
offline <- readData("offline.final.trace.txt")
# fix up the xypos
offline$posXY <- paste(offline$posX, offline$posY, sep = "-")
byLocAngleAP = with(offline, by(offline, list(posXY, angle, mac), function(x) x))

signalSummary = lapply(byLocAngleAP, function(oneLoc) {
    ans = oneLoc[1, ]
    ans$medSignal = median(oneLoc$signal)
    ans$avgSignal = mean(oneLoc$signal)
    ans$num = length(oneLoc$signal)
    ans$sdSignal = sd(oneLoc$signal)
    ans$iqrSignal = IQR(oneLoc$signal)
    ans
})
offlineSummary_original = do.call("rbind", signalSummary)
offlineSummary <- offlineSummary_original %>% filter(mac != router_b)

online <- readData("online.final.trace.txt", subMacs = unique(offlineSummary$mac))
online$posXY <- paste(online$posX, online$posY, sep = "-")

keepVars = c("posXY", "posX", "posY", "orientation", "angle")
byLoc = with(online, by(online, list(posXY), function(x) {
    ans = x[1, keepVars]
    avgSS = tapply(x$signal, x$mac, mean)
    y = matrix(avgSS, nrow = 1, ncol = 6, dimnames = list(ans$posXY, names(avgSS)))
    cbind(ans, y)
}))

onlineSummary = do.call("rbind", byLoc)
reshapeSS1 <- function(data, varSignal = "signal", keepVars = c("posXY", "posX", 
    "posY")) {
    byLocation <- with(data, by(data, list(posXY), function(x) {
        ans <- x[1, keepVars]
        avgSS <- tapply(x[, varSignal], x$mac, mean)
        y <- matrix(avgSS, nrow = 1, ncol = 6, dimnames = list(ans$posXY, names(avgSS)))
        cbind(ans, y)
    }))
    
    newDataSS <- do.call("rbind", byLocation)
    return(newDataSS)
}


selectTrain1 <- function(angleNewObs, signals = NULL, m = 1) {
    # m is the number of angles to keep between 1 and 5
    refs <- seq(0, by = 45, length = 8)
    nearestAngle <- roundOrientation(angleNewObs)
    
    if (m%%2 == 1) 
        angles <- seq(-45 * (m - 1)/2, 45 * (m - 1)/2, length = m) else {
        m = m + 1
        angles <- seq(-45 * (m - 1)/2, 45 * (m - 1)/2, length = m)
        if (sign(angleNewObs - nearestAngle) > -1) 
            angles <- angles[-1] else angles <- angles[-m]
    }
    # round angles
    angles <- angles + nearestAngle
    angles[angles < 0] <- angles[angles < 0] + 360
    angles[angles > 360] <- angles[angles > 360] - 360
    angles <- sort(angles)
    
    offlineSubset <- signals[signals$angle %in% angles, ]
    reshapeSS1(offlineSubset, varSignal = "avgSignal")
}


findNN1 <- function(newSignal, trainSubset) {
    diffs <- apply(trainSubset[, 4:9], 1, function(x) x - newSignal)
    dists <- apply(diffs, 2, function(x) sqrt(sum(x^2)))
    closest <- order(dists)
    weightDF <- trainSubset[closest, 1:3]
    weightDF$weight <- 1/closest
    return(weightDF)
}


predXY1 <- function(newSignals, newAngles, trainData, numAngles = 1, k = 3) {
    closeXY <- list(length = nrow(newSignals))
    
    for (i in 1:nrow(newSignals)) {
        trainSS <- selectTrain1(newAngles[i], trainData, m = numAngles)
        closeXY[[i]] <- findNN1(newSignal = as.numeric(newSignals[i, ]), trainSS)
    }
    
    estXY <- lapply(closeXY, function(x) sapply(x[, 2:3], function(x) mean(x[1:k])))
    estXY <- do.call("rbind", estXY)
    return(estXY)
}
byLocAngleAP = with(offline, by(offline, list(posXY, angle, mac), function(x) x))

signalSummary = lapply(byLocAngleAP, function(oneLoc) {
    ans = oneLoc[1, ]
    ans$medSignal = median(oneLoc$signal)
    ans$avgSignal = mean(oneLoc$signal)
    ans$num = length(oneLoc$signal)
    ans$sdSignal = sd(oneLoc$signal)
    ans$iqrSignal = IQR(oneLoc$signal)
    ans
})

offlineSummary_original = do.call("rbind", signalSummary)
offlineSummary <- offlineSummary_original %>% filter(mac != router_b)


keepVars = c("posXY", "posX", "posY", "orientation", "angle")
byLoc = with(online, by(online, list(posXY), function(x) {
    ans = x[1, keepVars]
    avgSS = tapply(x$signal, x$mac, mean)
    y = matrix(avgSS, nrow = 1, ncol = 6, dimnames = list(ans$posXY, names(avgSS)))
    cbind(ans, y)
}))

onlineSummary = do.call("rbind", byLoc)
estXYk3 = predXY1(newSignals = onlineSummary[, 6:11], newAngles = onlineSummary[, 
    4], offlineSummary, numAngles = 3, k = NNeighbors)

# nearest neighbor
estXYk1 = predXY1(newSignals = onlineSummary[, 6:11], newAngles = onlineSummary[, 
    4], offlineSummary, numAngles = 3, k = 1)
v = 11
permuteLocs = sample(unique(offlineSummary$posXY))
permuteLocs = matrix(permuteLocs, ncol = v, nrow = floor(length(permuteLocs)/v))

onlineFold = subset(offlineSummary, posXY %in% permuteLocs[, 1])
reshapeSS1 = function(data, varSignal = "signal", keepVars = c("posXY", "posX", 
    "posY"), sampleAngle = FALSE, refs = seq(0, 315, by = 45)) {
    byLocation = with(data, by(data, list(posXY), function(x) {
        if (sampleAngle) {
            x = x[x$angle == sample(refs, size = 1), ]
        }
        ans = x[1, keepVars]
        avgSS = tapply(x[, varSignal], x$mac, mean)
        y = matrix(avgSS, nrow = 1, ncol = 6, dimnames = list(ans$posXY, names(avgSS)))
        cbind(ans, y)
    }))
    
    newDataSS = do.call("rbind", byLocation)
    return(newDataSS)
}


offline = offline[offline$mac != "00:0f:a3:39:dd:cd", ]

keepVars = c("posXY", "posX", "posY", "orientation", "angle")

onlineCVSummary = reshapeSS1(offline, keepVars = keepVars, sampleAngle = TRUE)

onlineFold = subset(onlineCVSummary, posXY %in% permuteLocs[, 1])

offlineFold = subset(offlineSummary, posXY %in% permuteLocs[, -1])

estFold = predXY1(newSignals = onlineFold[, 6:11], newAngles = onlineFold[, 
    4], offlineFold, numAngles = 1, k = 3)

actualFold = onlineFold[, c("posX", "posY")]
NNeighbors = 20
K = NNeighbors
err = numeric(K)

for (j in 1:v) {
    onlineFold = subset(onlineCVSummary, posXY %in% permuteLocs[, j])
    offlineFold = subset(offlineSummary, posXY %in% permuteLocs[, -j])
    actualFold = onlineFold[, c("posX", "posY")]
    
    for (k in 1:K) {
        estFold = predXY1(newSignals = onlineFold[, 6:11], newAngles = onlineFold[, 
            4], offlineFold, numAngles = 1, k = k)
        err[k] = err[k] + calcError(estFold, actualFold)
    }
}
```