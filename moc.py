# ----------------------------------------------------
# Hands-on: Simulating Unsteady Flow with MOC
# Course: Advanced Hydraulics
# ----------------------------------------------------

import numpy as np
import matplotlib.pyplot as plt
import matplotlib.animation as animation

# --- 1. Channel and Flow Parameters ---
L = 20000.0      # Channel length (m)
B = 25.0         # Channel width (m)
n = 0.025        # Manning's roughness coefficient
S0 = 0.0002      # Bed slope (mild slope)
g = 9.81         # Gravity (m/s^2)

# --- 2. Numerical Discretization ---
num_nodes = 51   # Number of spatial nodes
dx = L / (num_nodes - 1)
x = np.linspace(0, L, num_nodes)

# Choose dt based on CFL condition
# We'll calculate it later, but start with a guess.
dt = 20.0        # Time step (s)
T_sim = 5 * 3600 # Total simulation time (5 hours)
num_timesteps = int(T_sim / dt)

# --- 3. Initial Conditions (Steady, uniform flow) ---
Q_base = 100.0   # Base flow (m^3/s)

# To find initial uniform depth (y_norm), we solve Manning's equation for Q_base
# Q = (1/n) * A * R^(2/3) * S0^(1/2)
# This requires an iterative solver, but for a wide channel (B >> y), R ≈ y
# So, Q ≈ (1/n) * (B*y) * y^(2/3) * S0^(1/2) => y ≈ (Q*n / (B*S0^0.5))^(3/5)
y_norm = (Q_base * n / (B * S0**0.5))**(3/5)
v_norm = Q_base / (B * y_norm)

print(f"Initial uniform depth (y_norm): {y_norm:.2f} m")
print(f"Initial uniform velocity (v_norm): {v_norm:.2f} m/s")

# Initialize arrays for depth (y) and velocity (v)
y = np.full((num_timesteps, num_nodes), y_norm)
v = np.full((num_timesteps, num_nodes), v_norm)

# Check initial CFL condition
c_norm = np.sqrt(g * y_norm)
cfl_initial = (v_norm + c_norm) * dt / dx
print(f"Initial CFL number: {cfl_initial:.2f}. Ensure this is <= 1.0")
if cfl_initial > 1.0:
    print("FATAL: CFL condition not met. Reduce dt or increase dx.")
    # For the workshop, we can stop here if it's not met.
    # In a real model, you would adjust dt automatically.
    # Let's adjust dt automatically for robustness
    dt = 0.9 * dx / (v_norm + c_norm)
    num_timesteps = int(T_sim / dt)
    y = np.full((num_timesteps, num_nodes), y_norm)
    v = np.full((num_timesteps, num_nodes), v_norm)
    print(f"Adjusted dt to {dt:.2f}s to meet CFL condition.")


# --- 4. Boundary Conditions ---
# Upstream BC: Inflow hydrograph (a flood wave)
t_hydro = np.arange(0, T_sim, dt)
Q_peak = 500.0
t_peak = 1.5 * 3600 # Peak at 1.5 hours
hydrograph = Q_base + (Q_peak - Q_base) * np.exp(-((t_hydro - t_peak)**2) / (2 * (3600**2)))

# --- 5. The Main Simulation Loop ---
for t in range(num_timesteps - 1):
    
    # --- UPSTREAM BOUNDARY (j=0) ---
    # We have Q from hydrograph, need to find y and v using the C- characteristic
    Q_in = hydrograph[t+1]
    
    # C- characteristic from node j=1 at previous time
    y_B = y[t, 1]
    v_B = v[t, 1]
    R_B = (B * y_B) / (B + 2*y_B)
    Sf_B = (n**2 * v_B**2) / (R_B**(4/3))
    c_B = np.sqrt(g * y_B)
    
    Cm = v_B - (g/c_B)*y_B + g*(S0 - Sf_B)*dt
    
    # At the boundary, we have Q_in = v_p * A_p = v_p * (B * y_p)
    # v_p = Q_in / (B * y_p)
    # Substitute this into the C- equation: Q_in/(B*y_p) - (g/c_B)*y_p = Cm
    # This is a non-linear equation for y_p. For simplicity, we can linearize or iterate.
    # Let's use a simple trial-and-error approach (or Newton-Raphson for advanced).
    # Simplified approach: use previous celerity. v_p = Cm + (g/c_B)*y_p
    # Q_in = (Cm + (g/c_B)*y_p) * B * y_p  => a quadratic equation in y_p
    # (B*g/c_B)*y_p^2 + (B*Cm)*y_p - Q_in = 0
    a_quad = B * g / c_B
    b_quad = B * Cm
    c_quad = -Q_in
    y[t+1, 0] = (-b_quad + np.sqrt(b_quad**2 - 4*a_quad*c_quad)) / (2*a_quad)
    v[t+1, 0] = Q_in / (B * y[t+1, 0])

    # --- INTERNAL NODES (j=1 to num_nodes-2) ---
    for j in range(1, num_nodes - 1):
        # Point A is node j-1, Point B is node j+1
        y_A, v_A = y[t, j-1], v[t, j-1]
        y_B, v_B = y[t, j+1], v[t, j+1]

        # Properties at A
        R_A = (B * y_A) / (B + 2*y_A)
        Sf_A = (n**2 * v_A**2) / (R_A**(4/3))
        c_A = np.sqrt(g * y_A)

        # Properties at B
        R_B = (B * y_B) / (B + 2*y_B)
        Sf_B = (n**2 * v_B**2) / (R_B**(4/3))
        c_B = np.sqrt(g * y_B)
        
        # Check CFL for this specific point, it can vary
        cfl_A = (abs(v_A) + c_A) * dt / dx
        cfl_B = (abs(v_B) + c_B) * dt / dx
        if cfl_A > 1 or cfl_B > 1:
            print(f"Warning: CFL > 1 at t={t*dt:.0f}s, j={j}")
        
        # Calculate compatibility constants
        Cp = v_A + (g/c_A)*y_A - g*(S0 - Sf_A)*dt
        Cm = v_B - (g/c_B)*y_B - g*(S0 - Sf_B)*dt # Note: original had +g, fixed to -g for convention
        
        # Calculate v and y at point P (node j at t+1)
        v[t+1, j] = (Cp + Cm) / 2.0
        c_avg = (c_A + c_B) / 2.0
        y[t+1, j] = (Cp - Cm) * c_avg / (2 * g)

    # --- DOWNSTREAM BOUNDARY (j=num_nodes-1) ---
    # Assume uniform flow (rating curve where S_f = S_0)
    # C+ characteristic from node j-1
    y_A, v_A = y[t, -2], v[t, -2]
    R_A = (B * y_A) / (B + 2*y_A)
    Sf_A = (n**2 * v_A**2) / (R_A**(4/3))
    c_A = np.sqrt(g * y_A)
    
    Cp = v_A + (g/c_A)*y_A - g*(S0 - Sf_A)*dt
    
    # At the downstream end, Manning's equation holds: v_p = (1/n)*R_p^(2/3)*S0^0.5
    # This is also non-linear. Let's assume R_p ≈ y_p (wide channel)
    # v_p = (S0^0.5/n) * y_p^(2/3)
    # From C+ characteristic: v_p = Cp - (g/c_A)*y_p
    # (S0^0.5/n) * y_p^(2/3) = Cp - (g/c_A)*y_p
    # We can solve this iteratively. A simple fixed-point iteration:
    y_guess = y[t, -1] # Start with previous depth
    for _ in range(3): # Iterate a few times for convergence
        R_guess = (B * y_guess) / (B + 2*y_guess)
        v_manning = (S0**0.5 / n) * R_guess**(2/3)
        v_char = Cp - (g/c_A)*y_guess
        # A better approach: solve for y using the characteristic eq
        # v_p = Cp - (g/c_A)*y_p
        # For wide channel: v_p ≈ (S0^0.5/n) * y_p^(2/3)
        # We'll use the previous timestep y as an approximation for R to simplify
        R_prev = (B * y[t,-1]) / (B+2*y[t,-1])
        y[t+1, -1] = ( (Cp - ( (S0**0.5/n) * R_prev**(2/3) ) ) * c_A) / g
        v[t+1, -1] = (S0**0.5 / n) * ((B*y[t+1,-1])/(B+2*y[t+1,-1]))**(2/3)
        
print("Simulation finished.")

# --- 6. Visualization ---
Q = v * (B * y) # Calculate discharge for plotting

# --- Static Plot: Water Surface Profiles at different times ---
plt.figure(figsize=(12, 7))
plt.plot(x/1000, y[0, :], label=f't = 0 hrs')
plt.plot(x/1000, y[int(num_timesteps/2.5), :], label=f't = {T_sim/3600/2.5:.1f} hrs (Peak Inflow)')
plt.plot(x/1000, y[int(num_timesteps-1), :], label=f't = {T_sim/3600:.1f} hrs (End)')
plt.title('Flood Wave Propagation: Water Surface Profile')
plt.xlabel('Distance (km)')
plt.ylabel('Water Depth (m)')
plt.legend()
plt.grid(True)
plt.show()

# --- Static Plot: Hydrographs at different locations ---
plt.figure(figsize=(12, 7))
time_hours = np.arange(num_timesteps) * dt / 3600
plt.plot(time_hours, Q[:, 0], label='Upstream (x=0 km)')
plt.plot(time_hours, Q[:, int(num_nodes/2)], label=f'Mid-channel (x={L/2000:.0f} km)')
plt.plot(time_hours, Q[:, -1], label=f'Downstream (x={L/1000:.0f} km)')
plt.title('Flood Hydrograph Attenuation')
plt.xlabel('Time (hours)')
plt.ylabel('Discharge (m^3/s)')
plt.legend()
plt.grid(True)
plt.show()


# --- Dynamic Animation ---
fig, ax = plt.subplots(figsize=(12, 7))
ax.set_ylim(0, y.max() * 1.2)
ax.set_xlim(0, L / 1000)
ax.set_xlabel('Distance (km)')
ax.set_ylabel('Water Depth (m)')
ax.set_title('Flood Wave Simulation')
ax.grid(True)

# Plot the channel bed
bed_elevation = np.zeros_like(x) # We can make this more complex later
water_surface_initial = bed_elevation + y[0, :]
line, = ax.plot(x / 1000, water_surface_initial, lw=2)
ax.plot(x / 1000, bed_elevation, 'k-', lw=1.5, label='Channel Bed')
time_text = ax.text(0.02, 0.90, '', transform=ax.transAxes)

def update(frame):
    # Update the water surface line
    water_surface = bed_elevation + y[frame, :]
    line.set_ydata(water_surface)
    
    # Update the time text
    time_text.set_text(f'Time: {frame * dt / 3600:.2f} hours')
    
    return line, time_text

# Create the animation
# Use a smaller number of frames for faster animation generation, e.g., range(0, num_timesteps, 10)
ani = animation.FuncAnimation(fig, update, frames=range(0, num_timesteps, 20),
                              blit=True, interval=50)

# To save the animation (requires ffmpeg or other writer)
# ani.save('flood_wave.mp4', writer='ffmpeg', fps=30)

plt.legend()
plt.show()