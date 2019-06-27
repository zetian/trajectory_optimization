import osqp
import time
import random
import numpy as np
import scipy as sp
import scipy.sparse as sparse
from scipy.linalg import block_diag
from systems import *
from matplotlib import pyplot as plt
import copy

class iterative_MPC_optimizer:
    def __init__(self, sys, target_states, dt):
        self.target_states = target_states
        self.horizon = self.target_states.shape[0]
        self.dt = dt
        self.converge = False
        self.system = sys
        self.n_states = sys.state_size
        self.m_inputs = sys.control_size
        self.Q = sys.Q
        self.R = sys.R
        self.Qf = sys.Q_f
        self.maxIter = 20
        self.min_cost = 0.0
        self.LM_parameter = 0.0
        self.eps = 1e-3
        self.states = np.zeros((self.horizon, self.n_states))
        self.inputs = np.zeros((self.horizon - 1, self.m_inputs))

    def sim(self, x0, inputs):
        states = np.zeros((self.horizon, self.n_states))
        states[0, :] = x0
        for i in range(self.horizon - 1):
            states[i + 1, :] = self.system.model_f(states[i], inputs[i])
        return states

    def cost(self):
        states_diff = self.states - self.target_states
        cost = 0.0
        for i in range(self.horizon - 1):
            state = np.reshape(states_diff[i, :], (-1, 1))
            control = np.reshape(self.inputs[i, :], (-1, 1))
            cost += np.dot(np.dot(state.T, self.Q), state) + \
                np.dot(np.dot(control.T, self.R), control)
        state = np.reshape(states_diff[-1, :], (-1, 1))
        cost += np.dot(np.dot(state.T, self.Qf), state)
        return cost
    
    def __call__(self):
        umin = np.array([-1.5, -0.2])
        umax = np.array([1.5, 0.2])
        xmin = np.array([-np.inf, -np.inf, 0.5, -np.inf])
        xmax = np.array([np.inf, np.inf, 1.5, np.inf])
        lineq = np.hstack([np.kron(np.ones(self.horizon), xmin), np.kron(np.ones(self.horizon - 1), umin)])
        uineq = np.hstack([np.kron(np.ones(self.horizon), xmax), np.kron(np.ones(self.horizon - 1), umax)])
        P = sparse.block_diag([sparse.kron(sparse.eye(self.horizon - 1), self.Q), self.Qf,
                            sparse.kron(sparse.eye(self.horizon - 1), self.R)]).tocsc()
        q = -self.Q.dot(self.target_states[0, :])
        for i in range(1, self.horizon - 1):
            q = np.hstack([q, -self.Q.dot(self.target_states[i, :])])
        q = np.hstack([q, -self.Qf.dot(self.target_states[-1, :]), np.zeros((self.horizon - 1)*self.m_inputs)])
        x0 = self.target_states[0, :]
        leq = np.hstack([-x0, np.zeros((self.horizon - 1)*self.n_states)])
        ueq = leq
        Aineq = sparse.eye(self.horizon*self.n_states + (self.horizon - 1)*self.m_inputs)
        l = np.hstack([leq, lineq])
        u = np.hstack([ueq, uineq])

        Bd = sparse.csc_matrix([
            [0, 0],
            [0, 0],
            [self.dt, 0],
            [0, self.dt]
        ])
        Bu = sparse.kron(sparse.vstack([sparse.csc_matrix((1, self.horizon - 1)), sparse.eye(self.horizon - 1)]), Bd)
        self.states = self.target_states
        self.min_cost = np.inf
        aux = np.empty((0, self.n_states), int)
        for iter in range(self.maxIter):
            Ad = []
            for i in range(self.horizon - 1):
                Ai = system.get_A(self.states[i, :], self.inputs[i, :])
                Ad.append(Ai)
            
            Ax_offset = block_diag(aux.T, *Ad, aux)
            Ax_offset = sparse.csr_matrix(Ax_offset)
            Ax = sparse.kron(sparse.eye(self.horizon),-sparse.eye(self.n_states)) + Ax_offset
            Aeq = sparse.hstack([Ax, Bu])
            A = sparse.vstack([Aeq, Aineq]).tocsc()

            prob = osqp.OSQP()
            prob.setup(P, q, A, l, u, warm_start=True, verbose=False)
            res = prob.solve()
            inputs = res.x[self.horizon*self.n_states:]
            self.inputs = np.reshape(inputs, (-1, 2))
            self.states = self.sim(x0, self.inputs)
            cost = self.cost()
            print(cost)
            if abs(1 - cost/self.min_cost) < self.eps or cost > self.min_cost:
                break
            else:
                self.min_cost = cost
            
eps = 1e-3
num_state = 4
num_input = 2
horizon = 80

ntimesteps = horizon
target_states = np.zeros((ntimesteps, 4))
noisy_targets = np.zeros((ntimesteps, 4))
noisy_targets[0, 2] = 1
target_states[0, 2] = 1
ref_vel = np.ones(ntimesteps)
# ref_vel = np.zeros(ntimesteps)
dt = 0.2
curv = 0.1
a = 1.5
v_max = 11

system = Car()
system.set_dt(dt)
system.set_cost(
    np.diag([500.0, 500.0, 100.0, 1]), np.diag([300.0, 1000.0]))
system.Q_f = system.Q*horizon*50
system.set_control_limit(np.array([[-1.5, 1.5], [-0.3, 0.3]]))
init_inputs = np.zeros((ntimesteps - 1, num_input))




# for i in range(40, ntimesteps):
#     if ref_vel[i - 1] > v_max:
#         a = 0
#     ref_vel[i] = ref_vel[i - 1] + a*dt
# random inputs case
for i in range(1, ntimesteps):
    target_states[i, 0] = target_states[i-1, 0] + \
        np.cos(target_states[i-1, 3])*dt*ref_vel[i - 1]
    target_states[i, 1] = target_states[i-1, 1] + \
        np.sin(target_states[i-1, 3])*dt*ref_vel[i - 1]
    target_states[i, 2] = ref_vel[i]
    target_states[i, 3] = target_states[i-1, 3] + curv*dt
    noisy_targets[i, 0] = target_states[i, 0] + random.uniform(0, 1)
    noisy_targets[i, 1] = target_states[i, 1] + random.uniform(0, 1)
    noisy_targets[i, 2] = ref_vel[i]
    noisy_targets[i, 3] = target_states[i, 3] + random.uniform(0, 0.1)

for i in range(1, ntimesteps):
    init_inputs[i - 1, 0] = (noisy_targets[i, 2] - noisy_targets[i - 1, 2])/dt
    init_inputs[i - 1, 1] = (noisy_targets[i, 3] - noisy_targets[i - 1, 3])/dt

# corner inputs case

# for i in range(1, 50):
#     target_states[i, 0] = target_states[i-1, 0] + dt*ref_vel[i - 1]
#     target_states[i, 1] = target_states[i-1, 1]
#     target_states[i, 2] = ref_vel[i]
#     target_states[i, 3] = 0
#     noisy_targets[i, 0] = target_states[i, 0]
#     noisy_targets[i, 1] = target_states[i, 1]
#     noisy_targets[i, 2] = target_states[i, 3]
#     noisy_targets[i, 3] = target_states[i, 3]

# for i in range(50, 80):
#     target_states[i, 0] = target_states[i-1, 0]
#     target_states[i, 1] = target_states[i-1, 1] + dt*ref_vel[i - 1]
#     target_states[i, 2] = ref_vel[i]
#     target_states[i, 3] = np.pi/2
#     noisy_targets[i, 0] = target_states[i, 0] 
#     noisy_targets[i, 1] = target_states[i, 1]
#     noisy_targets[i, 2] = target_states[i, 3]
#     noisy_targets[i, 3] = target_states[i, 3]

# for i in range(1, ntimesteps):
#     init_inputs[i - 1, 0] = (noisy_targets[i, 2] - noisy_targets[i - 1, 2])/dt
#     init_inputs[i - 1, 1] = (noisy_targets[i, 3] - noisy_targets[i - 1, 3])/dt

start = time.time()
mpc_optimizer= iterative_MPC_optimizer(system, noisy_targets, dt)
mpc_optimizer.inputs = init_inputs
mpc_optimizer()
states = mpc_optimizer.states

end = time.time()
print(end - start)
# print(cnt)
plt.figure(figsize=(8*1.1, 6*1.1))
plt.title('MPC: 2D, x and y.  ')
plt.axis('equal')
plt.plot(target_states[:, 0], target_states[:, 1], '--g', label='Target', linewidth=2)
plt.plot(noisy_targets[:, 0], noisy_targets[:, 1], '--r', label='Target', linewidth=2)
# plt.plot(mpc_optimizer.states[:, 0], mpc_optimizer.states[:, 1], '-+b', label='MPC', linewidth=1.0)
plt.plot(states[:, 0], states[:, 1], '-+b', label='MPC', linewidth=1.0)
plt.xlabel('x (meters)')
plt.ylabel('y (meters)')
plt.figure(figsize=(8*1.1, 6*1.1))
plt.title('iLQR: state vs. time.  ')
plt.plot(states[:, 2], '-b', linewidth=1.0, label='speed')
plt.plot(ref_vel, '-r', linewidth=1.0, label='target speed')
plt.ylabel('speed')
plt.show()



