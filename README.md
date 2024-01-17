# MSFS VKB FSM-GA Connector

This repo contains example code for syncing the LEDs of the
VKB FMS-GA with MSFS via SimConnect.

## Usage

### Setup 

Install Python 3.

Clone or download this repo.

Inside this repo directory create a virtual environment:

```powershell
python -m venv venv
```

Activate the virtual environment:

```powershell
.\venv\Scripts\activate
```

Install the dependencies
```powershell
pip install -r requirements.txt
```

### Perform a self test

```powershell
python main.py test
```

### Start the sync

```powershell
python main.py
```

## Dev notes

### Sync update loop

The sync update loop checks the state of the sim using SimConnect.

Each LED ID has an update function that receives the instance of the
SimConnect AircraftRequests with which it is responsible for setting
the LED to the correct state. This results in more verbose code but
more flexibility and easy readability.



