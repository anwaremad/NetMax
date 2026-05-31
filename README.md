# NetMax
<img width="1536" height="1024" alt="Net Max Application" src="https://github.com/user-attachments/assets/ca62d66e-1670-4d4a-8999-4bdb7780a926" />
A powerful Windows network monitoring tool designed to provide real-time visibility into internet usage, bandwidth consumption, active connections, and network performance.

## Version

**NetMax v1.0.0** - Initial Release

## Features

### Real-Time Network Monitoring

* Monitor download speed in real time.
* Monitor upload speed in real time.
* Track total network activity continuously.
* Live bandwidth usage statistics.

### Active Connections Monitoring

* View active network connections.
* Monitor currently connected processes.
* Identify applications using internet resources.

### Ping Monitoring

* Measure network latency (Ping).
* Track connection responsiveness.
* Detect network performance issues.

### Usage Analytics

* Internet usage during the current day.
* Internet usage during the current month.
* Internet usage during the last 24 hours.
* Historical traffic tracking.

### Application Bandwidth Analysis

* Monitor internet consumption per application.
* Identify bandwidth-heavy programs.
* Analyze which software is using your connection.

### Traffic Analysis

* Detailed analysis for the last hour.
* Detailed analysis for the last 24 hours.
* Network activity insights and usage trends.

### Performance Optimized

* Lightweight design.
* Minimal CPU and memory usage.
* Continuous background monitoring.

## Why NetMax?

NetMax was created to give users a clear understanding of how their internet connection is being used. Unlike many complicated monitoring solutions, NetMax focuses on simplicity while providing powerful real-time analytics and bandwidth tracking capabilities.

## Technologies Used

### Programming Language

* Python

### Core Libraries

* psutil
* socket
* threading
* datetime
* sqlite3

### User Interface

* Tkinter / CustomTkinter

### Additional Components

* Pillow (Icons and Images)
* Windows APIs (System Information)

## How NetMax Works

NetMax continuously monitors network adapters and active connections through the operating system. It collects real-time traffic statistics, calculates upload and download speeds, records usage history, measures latency, and analyzes bandwidth consumption by individual applications.

## Current Release

This is the first public release of NetMax.

Version 1.0 introduces:

* Real-time download monitoring
* Real-time upload monitoring
* Active connections tracking
* Ping measurement
* Daily usage statistics
* Monthly usage statistics
* Last 24 hours usage tracking
* Per-application bandwidth monitoring
* Last hour traffic analysis
* Last 24 hours traffic analysis

## Future Plans

* Export reports to CSV and Excel
* Advanced charts and graphs
* Network alerts and notifications
* Multiple network adapter support
* Speed test integration
* Dark and Light themes
* Cloud backup for statistics

## Developer

Developed by Abdo Emad.

## License

This project is released for educational and personal use.
