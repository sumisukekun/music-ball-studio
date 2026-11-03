import numpy as np, json, sim, mido
SEED = 127
p0, v0 = sim.init(SEED)
P, V, lt, sl, ev = sim.run(p0, v0, sim.PEG, sim.SEG, sim.SPN, sim.G, sim.TMAX)
winner = int(np.argmax(lt))
# music timing: Entertainer, cadence at the downbeat of bar 36 = jackpot landing
T0 = 0.4
T_LAND = 55.0
# gate opens on the downbeat of bar 2
bar = None
# solve: gate = T0 + bar ; T_LAND = gate + lt_w * s ; T_LAND = T0 + 35*bar
bar = (T_LAND - T0) / 35
gate = T0 + bar
s = (T_LAND - gate) / lt[winner]
np.savez('/home/claude/vegas/simres.npz', P=P, V=V, lt=lt, sl=sl, ev=ev, p0=p0)
json.dump(dict(seed=SEED, winner=winner, T0=T0, bar=bar, gate=gate, s=s, T_LAND=T_LAND, END=T_LAND + 8.5,
               lt=lt.tolist(), sl=sl.tolist()), open('/home/claude/vegas/timing.json', 'w'))
print('winner', winner, 'bar', round(bar, 3), 'q=', round(120 / bar, 1), 'gate', round(gate, 2), 'scale', round(s, 3))
print('land video times', [round(gate + x * s, 1) for x in lt], 'slots', sl.tolist(), 'events', len(ev))
