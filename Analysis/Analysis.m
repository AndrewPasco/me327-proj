clc; clear; close all;

% estimated motor mounting housing weight: 150g
m = 150 * 1/1000;      % kg

kh = 1000;     % N/m
zetah = 2;
wn = sqrt(kh/m);
dh = (2*zetah*wn)/m;     % N s/m

% scaling factor
scale = 10;
zetab = 1;
kb = kh*scale;     % N/m
wnb = sqrt(kb/m);
db = (2*zetab*wnb)/m;     % N s/m


% erm properties:
% 13000 RPM
% 0.5 g eccentric mass
% 2.5 mm
merm = 0.5 * 1/1000;   % kg
rerm = 2.5 * 1/1000;   % m
werm = 13000* 1/60 * 2*pi;   % rad/s

Fpeak = merm*werm^2*rerm;



A1 = [ 0   1   0   0  ;
     -kb -db  kb  db ;
      0   0   0   1  ;
      kb  db -kb -db];
A2 = [ 0     1      0     0     ;
     -kb-kh -db-dh  kb    db    ;
      0      0      0     1     ; 
      kb     db   -kb-kh -db-dh];

B = [0;1/m;0;0];
C = [1 0 0 0;
     0 0 1 0];
D = 0;

syms s

C*(s*eye(4)-A1)^(-1)*B;


t = linspace(0,0.1,1000);
u = Fpeak*cos(werm*t);

sys1 = ss(A1,B,C,D);
sys2 = ss(A2,B, C,D);

y1 = lsim(sys1,u,t);
y2 = lsim(sys2,u,t);

figure(1)
plot(t,y1*1000)
title("Unconstrained Belt")
xlabel("time (s)")
ylabel("displacement (mm)")
legend("x_1","x_2")

figure(2)
plot(t,y2*1000)
title("Belt on Person")
xlabel("time (s)")
ylabel("displacement (mm)")
legend("x_1","x_2")