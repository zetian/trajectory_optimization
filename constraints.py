import numpy as np


class CircleConstraintForCar:
    def __init__(self, center, r, system):
        self.center = center
        self.r = r
        self.system = system

    def evaluate_constraint(self, x):
        # evolve the system for one to evaluate constraint
        x_next = self.system.transition(x, np.zeros(self.system.control_size))
        length = (x_next[0] - self.center[0])**2 + (x_next[1] - self.center[1])**2
        return self.r**2 - length

    def evaluate_constraint_J(self, x):
        # evolve the system for one to evaluate constraint
        x_next = self.system.transition(x, np.zeros(self.system.control_size))
        result = np.zeros(x.shape)
        result[0] = -2*(x_next[0] - self.center[0])
        result[1] = -2*(x_next[1] - self.center[1])
        result[2] = -2*(x_next[0] - self.center[0]) * self.system.dt
        result[3] = -2*(x_next[1] - self.center[1]) * self.system.dt
        return result