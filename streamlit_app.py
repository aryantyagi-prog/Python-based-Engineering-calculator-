import streamlit as st
import math

st.title("⚙️ Python Engineering Calculator")

st.write("Select a function below:")

option = st.selectbox(
    "Choose a calculation",
    [
        "Basic Arithmetic",
        "Quadratic Equation Solver",
        "Trigonometry",
        "Force Calculation (F = m * a)",
        "Ohm's Law (V = I * R)"
    ]
)

if option == "Basic Arithmetic":
    a = st.number_input("Enter first number:")
    b = st.number_input("Enter second number:")
    op = st.selectbox("Operation", ["Add", "Subtract", "Multiply", "Divide"])

    if st.button("Calculate"):
        if op == "Add":
            st.success(a + b)
        elif op == "Subtract":
            st.success(a - b)
        elif op == "Multiply":
            st.success(a * b)
        elif op == "Divide":
            if b != 0:
                st.success(a / b)
            else:
                st.error("Division by zero!")

elif option == "Quadratic Equation Solver":
    a = st.number_input("Enter a (coefficient of x²):", value=1.0)
    b = st.number_input("Enter b (coefficient of x):", value=0.0)
    c = st.number_input("Enter c (constant):", value=0.0)

    if st.button("Solve"):
        discriminant = b**2 - 4*a*c
        if discriminant < 0:
            st.error("No real roots.")
        else:
            x1 = (-b + math.sqrt(discriminant)) / (2*a)
            x2 = (-b - math.sqrt(discriminant)) / (2*a)
            st.success(f"Roots: {x1}, {x2}")

elif option == "Trigonometry":
    angle = st.number_input("Enter angle (degrees):", value=0.0)
    rad = math.radians(angle)

    st.write(f"sin({angle}) = {math.sin(rad):.4f}")
    st.write(f"cos({angle}) = {math.cos(rad):.4f}")
    st.write(f"tan({angle}) = {math.tan(rad):.4f}")

elif option == "Force Calculation (F = m * a)":
    mass = st.number_input("Enter mass (kg):", value=0.0)
    acc = st.number_input("Enter acceleration (m/s²):", value=0.0)

    if st.button("Calculate Force"):
        force = mass * acc
        st.success(f"Force = {force} N")

elif option == "Ohm's Law (V = I * R)":
    current = st.number_input("Enter current (A):", value=0.0)
    resistance = st.number_input("Enter resistance (Ω):", value=0.0)

    if st.button("Calculate Voltage"):
        voltage = current * resistance
        st.success(f"Voltage = {voltage} V")
