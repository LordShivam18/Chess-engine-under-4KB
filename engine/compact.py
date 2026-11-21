import base64
import json
import os
import sys
import urllib.request

W = 0
B = 8
P = 1
N = 2
BI = 3
R = 4
Q = 5
K = 6

CM = {"K": 1, "Q": 2, "k": 4, "q": 8}
RM = {28: 1, 21: 2, 98: 4, 91: 8}
PR = (Q, R, BI, N)
KN = (-21, -19, -12, -8, 8, 12, 19, 21)
KG = (-11, -10, -9, -1, 1, 9, 10, 11)
BD = (-11, -9, 9, 11)
RD = (-10, -1, 1, 10)
PC = {c: i % 6 + 1 | (8 if i > 5 else 0) for i, c in enumerate("PNBRQKpnbrqk")}


def on(s):
    return 21 <= s < 99 and 1 <= s % 10 < 9


SQ = tuple(s for s in range(120) if on(s))


def mk(D, ray=0):
    table = []
    for s in range(120):
        lines = []
        for d in D:
            line = []
            x = s + d
            while on(x):
                line.append(x)
                if not ray:
                    break
                x += d
            lines += [line] if ray else line
        table.append(lines)
    return table


KT = mk(KN)
GT = mk(KG)
BR = mk(BD, 1)
RR = mk(RD, 1)
QR = [BR[s] + RR[s] for s in range(120)]


def nm(s):
    return "abcdefgh"[s % 10 - 1] + str(s // 10 - 1)


def ps(s):
    return (int(s[1]) + 1) * 10 + "abcdefgh".index(s[0]) + 1


def uci(m):
    return nm(m[0]) + nm(m[1]) + (" nbrq"[m[2] - 1] if m[2] else "")


class Pos:
    def __init__(self, fen):
        self.load(fen)

    def load(self, fen):
        F = fen.split()
        b = [0] * 120
        for r, text in enumerate(F[0].split("/")):
            q = 0
            for ch in text:
                if ch.isdigit():
                    q += int(ch)
                else:
                    b[(9 - r) * 10 + q + 1] = PC[ch]
                    q += 1
        self.b = b
        self.s = 8 if F[1] == "b" else 0
        c = 0
        if F[2] != "-":
            for ch in F[2]:
                c |= CM[ch]
        self.c = c
        self.e = 0 if F[3] == "-" else ps(F[3])
        self.h = int(F[4])
        self.m = int(F[5])
        k = [0, 0]
        for s in SQ:
            p = b[s]
            if p & 7 == K:
                k[p >> 3] = s
        self.k = k
        self.st = []

    def att(self, s, by):
        b = self.b
        if by == W:
            if b[s - 9] == P or b[s - 11] == P:
                return 1
        elif b[s + 9] == P | B or b[s + 11] == P | B:
            return 1
        for t in KT[s]:
            if b[t] == N | by:
                return 1
        for t in GT[s]:
            if b[t] == K | by:
                return 1
        for line in BR[s]:
            for t in line:
                p = b[t]
                if p:
                    if p == BI | by or p == Q | by:
                        return 1
                    break
        for line in RR[s]:
            for t in line:
                p = b[t]
                if p:
                    if p == R | by or p == Q | by:
                        return 1
                    break
        return 0

    def chk(self):
        return self.att(self.k[self.s >> 3], self.s ^ B)

    def moves(self):
        b = self.b
        us = self.s
        th = us ^ B
        c = self.c
        e = self.e
        out = []
        for s in SQ:
            p = b[s]
            if not p or p & 8 != us:
                continue
            t = p & 7
            if t == P:
                r = s // 10 - 2
                d = 10 if us == W else -10
                a = s + d
                pr = 6 if us == W else 1
                if not b[a]:
                    if r == pr:
                        for q in PR:
                            out.append((s, a, q, 0))
                    else:
                        out.append((s, a, 0, 0))
                        if r == (1 if us == W else 6) and not b[a + d]:
                            out.append((s, a + d, 0, 1))
                for dd in ((9, 11) if us == W else (-9, -11)):
                    a = s + dd
                    v = b[a]
                    if v and v & 8 != us:
                        if r == pr:
                            for q in PR:
                                out.append((s, a, q, 0))
                        else:
                            out.append((s, a, 0, 0))
                    elif a == e:
                        out.append((s, a, 0, 2))
            elif t == N:
                for a in KT[s]:
                    v = b[a]
                    if not v or v & 8 != us:
                        out.append((s, a, 0, 0))
            elif t in (BI, R, Q):
                for line in (BR[s] if t == BI else RR[s] if t == R else QR[s]):
                    for a in line:
                        v = b[a]
                        if not v:
                            out.append((s, a, 0, 0))
                            continue
                        if v & 8 != us:
                            out.append((s, a, 0, 0))
                        break
            elif t == K:
                for a in GT[s]:
                    v = b[a]
                    if not v or v & 8 != us:
                        out.append((s, a, 0, 0))
                h = 20 if us == W else 90
                if s == h + 5:
                    if (c & (1 if us == W else 4) and not b[h + 6] and not b[h + 7]
                            and b[h + 8] == us | R and not self.att(h + 5, th)
                            and not self.att(h + 6, th) and not self.att(h + 7, th)):
                        out.append((h + 5, h + 7, 0, 3))
                    if (c & (2 if us == W else 8) and not b[h + 4] and not b[h + 3]
                            and not b[h + 2] and b[h + 1] == us | R
                            and not self.att(h + 5, th) and not self.att(h + 4, th)
                            and not self.att(h + 3, th)):
                        out.append((h + 5, h + 3, 0, 4))
        return out

    def legal(self):
        us = self.s
        th = us ^ B
        i = us >> 3
        out = []
        for m in self.moves():
            self.push(m)
            if not self.att(self.k[i], th):
                out.append(m)
            self.pop()
        return out

    def push(self, m):
        b = self.b
        us = self.s
        f, t, p, k = m
        pc = b[f]
        cs = t - 10 if k == 2 and us == W else t + 10 if k == 2 else t
        cap = b[cs]
        self.st.append((m, pc, cap, cs, self.c, self.e, self.h, us))
        b[f] = 0
        if cap:
            b[cs] = 0
        b[t] = p | us if p else pc
        if k == 3:
            h = 20 if us == W else 90
            b[h + 6] = b[h + 8]
            b[h + 8] = 0
        elif k == 4:
            h = 20 if us == W else 90
            b[h + 4] = b[h + 1]
            b[h + 1] = 0
        if pc & 7 == K:
            self.k[us >> 3] = t
        c = self.c
        if pc & 7 == K:
            c &= ~(3 if us == W else 12)
        c &= ~(RM.get(f, 0) | RM.get(cs, 0))
        self.c = c
        self.e = (f + t) // 2 if k == 1 else 0
        self.h = 0 if pc & 7 == P or cap else self.h + 1
        self.m += us == B
        self.s = us ^ B

    def pop(self):
        m, pc, cap, cs, c, e, h, us = self.st.pop()
        b = self.b
        b[m[0]] = pc
        b[m[1]] = 0
        if cap:
            b[cs] = cap
        if m[3] == 3:
            h0 = 20 if us == W else 90
            b[h0 + 8] = b[h0 + 6]
            b[h0 + 6] = 0
        elif m[3] == 4:
            h0 = 20 if us == W else 90
            b[h0 + 1] = b[h0 + 4]
            b[h0 + 4] = 0
        if pc & 7 == K:
            self.k[us >> 3] = m[0]
        self.s = us
        self.c = c
        self.e = e
        self.h = h
        self.m -= us == B
        return m

VAL = (0, 100, 320, 330, 500, 900, 0)
PST = tuple(v - 10 for v in base64.b85decode("1qccc4+;nc3Jnhw6b}sw4-ym^859x^85|xXBOV+XC@U>8GA%18K}1GNOGZRNUt(lwX=Gww1qccc4+;nc3=k9;7!(i;5EK|392gW36c`*JARHJJ7#tuZBp@6Z7#tuZBp@6Z6c`*JARHJJ5EK|392gW33=k9;7!(i;5E2v?78DW?5)>8~7#0)~6c!j78W<K778n{F92yuF78n{F92yuF6c!j78W<K75)>8~7#0)~5E2v?78DW?1O^BS3J3-S1_%la3<?Ma2nq}i4h#wi3JeYq5Dp9q3JeYq5Dp9q2nq}i4h#wi8XO)VARZhV1O^BS3J3-S4-gR&5)lv&5D^j+6A}>+5fT#=6cZ8=5)%{^6%-Q^5)%{^6%-Q^5fT#=6cZ8=5D^j+6A}>+4-gR&5)lv&Fd`lr8Xh7rEFKyb78)Kb9uN!&2n-M&8Vm>o1PBZo8Vm>o1PBZo9uN!&2n-M&A`}n|3=k9|CKwbD5EK|D"))

POS=None;NODES=0;LIMIT=50000;ABORT=False;MATE=99999
HIST={};KILL=[None]*64;TT={}
MASK=(1<<64)-1;Z=[];z=0x9E3779B97F4A7C15
for i in range(2000):
    z=(z*6364136223846793005+1442695040888963407)&MASK;Z.append(z)

def hsh():
    v=0
    for s in SQ:
        p=POS.b[s]
        if p:v^=Z[s*15+p+1]
    return v^Z[1801+POS.s]^Z[1810+POS.c]^Z[1826+POS.e]^POS.h

def pick(ms,tt=None,ply=0):
    def sc(m):
        if m==tt:return 1<<30
        v=POS.b[m[1]]
        if v:return (1<<20)+VAL[v&7]*10-VAL[POS.b[m[0]]&7]+VAL[m[2]]*10
        if m[2]:return (1<<20)+VAL[m[2]]*10
        if m[3]==2:return (1<<20)+VAL[P]*10-VAL[P]
        if KILL[ply]==m:return 1<<19
        return HIST.get(m,0)
    return sorted(ms,key=sc,reverse=True)


def ev():
    v=0
    for s in SQ:
        p=POS.b[s]
        if p:
            t=p&7;r=s//10-2;f=s%10-1
            i=r*8+f if p<8 else (7-r)*8+f
            x=VAL[t]+PST[(t-1)*64+i]
            v+=x if p<8 else -x
    return v if POS.s==W else -v


def qs(a,b,ply):
    global NODES,ABORT
    NODES+=1
    if NODES>=LIMIT:ABORT=True;return ev()
    if POS.chk():
        ms=POS.legal()
        if not ms:return -MATE+ply
    else:
        st=ev()
        if st>=b:return b
        if st>a:a=st
        if ply>=12:return a
        ms=[m for m in POS.legal() if POS.b[m[1]] or m[2] or m[3]==2]
    for m in pick(ms,None,ply):
        POS.push(m);v=-qs(-b,-a,ply+1);POS.pop()
        if ABORT:return a
        if v>=b:return b
        if v>a:a=v
    return a


def nega(d,a,b,ply):
    global NODES,ABORT
    NODES+=1
    if NODES>=LIMIT:ABORT=True;return ev()
    if d<=0:return qs(a,b,ply)
    oa=a;k=hsh();e=TT.get(k);tm=None
    if e:
        sd,sv,fl,tm=e
        if sd>=d:
            if fl==0:return sv
            if fl==1 and sv>=b:return sv
            if fl==2 and sv<=a:return sv
    ms=POS.legal()
    if not ms:return -MATE+ply if POS.chk() else 0
    best=-MATE;bm=None
    for m in pick(ms,tm,ply):
        POS.push(m);v=-nega(d-1,-b,-a,ply+1);POS.pop()
        if ABORT:return 0
        if v>best:best=v;bm=m
        if best>a:a=best
        if a>=b:
            if not POS.b[m[1]] and not m[2] and m[3]!=2:
                KILL[ply]=m;HIST[m]=HIST.get(m,0)+d*d
            break
    fl=2 if best<=oa else 1 if best>=b else 0
    if abs(best)<MATE-100:TT[k]=(d,best,fl,bm)
    return best


def root(d,cs,prev=None):
    global ABORT
    best=None;bs=-MATE;a=-MATE
    for m in pick(cs,prev,0):
        POS.push(m);v=-nega(d-1,-MATE,-a,1);POS.pop()
        if ABORT:return None
        if v>bs:bs=v;best=m
        if v>a:a=v
    return best,bs


def choose(fen,legal):
    global POS,NODES,ABORT
    POS=Pos(fen)
    by={uci(m):m for m in POS.legal()}
    cs=[by[x] for x in legal if x in by]
    if not cs:return legal[0] if legal else None
    best=cs[0];NODES=0;ABORT=False
    HIST.clear();TT.clear();KILL[:]=[None]*64
    for d in range(1,64):
        r=root(d,cs,best)
        if ABORT or r is None:break
        best=r[0]
        if abs(r[1])>MATE-100 or NODES>=LIMIT:break
    return uci(best)


ENV=""
def lim(o,p):
    q=o.split("-")if type(o)is str else []
    if len(q)==2 and q[0]=="depth" and q[1].isdigit():b=18000
    elif len(q)==2 and q[0]=="nodes" and q[1][:-1].isdigit() and q[1][-1:]in("k","M"):b=30000
    else:raise ValueError(o)
    return b//2 if p>100 else b*3//4 if p>60 else b
def post(p,b):
    r=urllib.request.Request(ENV+p,data=json.dumps(b).encode(),headers={"content-type":"application/json"})
    return json.load(urllib.request.urlopen(r))
def main():
    global ENV,LIMIT
    ENV=os.environ.get("MAKEFUN_ENV_URL","")
    if not ENV:sys.exit("MAKEFUN_ENV_URL is not set")
    while 1:
        g=post("/game",{})
        if g["status"]=="done":break
        while g["status"]=="your_move":
            L=g.get("legal_moves",[])
            LIMIT=lim(g["opponent"],g["plies"])
            try:m=choose(g["fen"],L) if L else None
            except:m=None
            if m not in L:m=L[0] if L else None
            if not m:
                post("/resign",{"game":g["game"]});break
            g=post("/move",{"game":g["game"],"move":m})
if __name__=="__main__":main()
