import matplotlib.pyplot as plt

from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
from matplotlib import ticker
import mysql.connector as ms
import tkinter as tk
from tkinter import ttk, messagebox
import numpy as np
from scipy import stats
import datetime

# Global variables
actual_data = []
estimated_data = []
prediction_made = False
mydb = None
tree_actual = None
tree_predicted = None

def connect_to_database():
    global mydb
    try:
        mydb = ms.connect(
            host="127.0.0.1",
            user="root",
            password="Ved@0902",
            database="financial_analysis"
        )
        print("Connected to database successfully")
    except ms.Error as e:
        print(f"Error connecting to MySQL database: {e}")
        messagebox.showerror("Database Error", f"Failed to connect to database: {e}")
        return None
    return mydb

def create_editable_treeview(parent, columns):
    tree = ttk.Treeview(parent, columns=columns, show='headings')
    for col in columns:
        tree.heading(col, text=col)
    tree.bind('<ButtonRelease-1>', on_click)
    return tree

def check_sflag(year):
    try:
        with mydb.cursor() as mycursor:
            sql = "SELECT SFLAG FROM year_on_year WHERE year = %s"
            mycursor.execute(sql, (year,))
            result = mycursor.fetchone()
            return result[0] if result else None
    except ms.Error as e:
        print(f"Error checking SFLAG: {e}")
        return None

def on_click(event):
    try:
        if not tree_actual.selection():
            print("No item selected")
            return
        item = tree_actual.selection()[0]
        column = tree_actual.identify_column(event.x)
        column_index = int(column.replace('#', '')) - 1
        print(f"Clicked on item: {item}, column: {column}, index: {column_index}")
        if column_index == 0: # Year column
            messagebox.showinfo("Info", "Year cannot be edited.")
            return
        year = int(tree_actual.item(item, 'values')[0])
        sflag = check_sflag(year)
        print(f"Year: {year}, SFLAG: {sflag}")
        if sflag is None:
            messagebox.showerror("Error", "Unable to check SFLAG.")
            return
        if sflag != 0:
            messagebox.showinfo("Info", "This value cannot be edited as it has been locked.")
            return
        value = tree_actual.set(item, column)
        edit_window = tk.Toplevel(root)
        edit_window.title("Edit Value")
        entry = tk.Entry(edit_window)
        entry.insert(0, value)
        entry.pack(padx=10, pady=10)
        entry.focus_set()
        def save_edit():
            new_value = entry.get()
            try:
                new_turnover = float(new_value) * 1000000 # Convert back to actual turnover value
                update_data_point(year, new_turnover)
                tree_actual.set(item, column, new_value)
                edit_window.destroy()
                update_plot()
                print(f"Value updated: Year {year}, New turnover {new_turnover}")
            except ValueError:
                messagebox.showerror("Error", "Invalid input. Please enter a number.")
        entry.bind('<Return>', lambda e: save_edit())
        save_button = tk.Button(edit_window, text="Save", command=save_edit)
        save_button.pack(pady=5)
    except Exception as e:
        print(f"Error in on_click: {e}")
        messagebox.showerror("Error", f"An error occurred: {e}")

def update_data_point(year, turnover):
    try:
        with mydb.cursor() as mycursor:
            sql = "UPDATE year_on_year SET turnover = %s WHERE year = %s AND SFLAG = 0"
            val = (turnover, year)
            mycursor.execute(sql, val)
            mydb.commit()
            if mycursor.rowcount > 0:
                print(f"Data point updated: Year {year}, Turnover {turnover}")
                # Update the actual_data list
                global actual_data
                actual_data = [(y, t) if y != year else (year, turnover) for y, t in actual_data]
            else:
                print(f"No update made: Year {year} is locked or doesn't exist.")
    except ms.Error as e:
        print(f"Error updating data point: {e}")
        mydb.rollback()

def fetch_data():
    try:
        with mydb.cursor() as mycursor:
            mycursor.execute("SELECT year, turnover, SFLAG FROM year_on_year ORDER BY year")
            return mycursor.fetchall()
    except ms.Error as e:
        print(f"Error fetching data: {e}")
        return []

def insert_data_point(year, turnover):
    try:
        with mydb.cursor() as mycursor:
            sql = "INSERT INTO year_on_year (year, turnover, SFLAG) VALUES (%s, %s, %s) ON DUPLICATE KEY UPDATE turnover = %s, SFLAG = %s"
            val = (year, turnover, 0, turnover, 0)
            mycursor.execute(sql, val)
            mydb.commit()
            print(f"Data point inserted/updated: Year {year}, Turnover {turnover}")
    except ms.Error as e:
        print(f"Error inserting/updating data point: {e}")
        mydb.rollback()

def set_sflag_to_one():
    try:
        with mydb.cursor() as mycursor:
            mycursor.execute("UPDATE year_on_year SET SFLAG = 1 WHERE year <= YEAR(CURDATE())")
            mydb.commit()
            print("SFLAG set to 1 for current and past years.")
    except ms.Error as e:
        print(f"Error setting SFLAG to 1: {e}")
        mydb.rollback()

def update_plot():
    ax.clear()
    if actual_data:
        actual_years, actual_turnovers = zip(*sorted(actual_data))
        ax.plot(actual_years, [t/1000000 for t in actual_turnovers], marker='o', linestyle='-', color='b', label='Historical Data')
    if estimated_data:
        estimated_years, estimated_turnovers = zip(*sorted(estimated_data))
        ax.plot(estimated_years, [t/1000000 for t in estimated_turnovers], marker='o', linestyle='-', color='r', label='Estimated Data')
      #  insert_data_point(estimated_years,estimated_turnovers )
    ax.set_title("Financial Analysis")
    ax.set_xlabel("Years")
    ax.set_ylabel("Turnover (in million $)")
    ax.grid(True)
    ax.legend()
    ax.xaxis.set_major_locator(ticker.MaxNLocator(integer=True))
    canvas.draw()
    
def update_table():
    tree_actual.delete(*tree_actual.get_children())
    for year, turnover in sorted(actual_data + estimated_data):
        color = 'black' if (year, turnover) in actual_data else 'red'
        tree_actual.insert('', 'end', values=(year, f"{turnover/1000000:.2f}"), tags=(color,))
    tree_actual.tag_configure('red', foreground='red')
   

def calculate_growth_rates(turnovers):
    return [(turnovers[i] - turnovers[i-1]) / turnovers[i-1] for i in range(1, len(turnovers))]

def monte_carlo_simulation(last_turnover, num_years, num_simulations, mu, sigma):
    simulations = np.zeros((num_simulations, num_years))
    for i in range(num_simulations):
        turnover = last_turnover
        for j in range(num_years):
            growth_rate = np.random.normal(mu, sigma)
            turnover *= (1 + growth_rate)
            simulations[i, j] = turnover
    return simulations

def run_monte_carlo_prediction(years, turnovers, num_years_to_predict=3, num_simulations=10000):
    growth_rates = calculate_growth_rates(turnovers)
    mu, sigma = stats.norm.fit(growth_rates)
    last_turnover = turnovers[-1]
    simulations = monte_carlo_simulation(last_turnover, num_years_to_predict, num_simulations, mu, sigma)
    median = np.median(simulations, axis=0)
    lower_bound = np.percentile(simulations, 10, axis=0)
    upper_bound = np.percentile(simulations, 90, axis=0)
    forecast_years = range(years[-1] + 1, years[-1] + num_years_to_predict + 1)
    return forecast_years, median, lower_bound, upper_bound

def predict():
    global prediction_made
    set_sflag_to_one()
    years, turnovers = zip(*sorted(actual_data))
    num_years_to_forecast = int(year_var.get())
    forecast_years, median, lower_bound, upper_bound = run_monte_carlo_prediction(years, turnovers, num_years_to_forecast)
    ax.plot(forecast_years, median/1000000, 'g--', label='Median Forecast')
    ax.fill_between(forecast_years, lower_bound/1000000, upper_bound/1000000, color='b', alpha=0.2, label='80% Confidence Interval')
    ax.legend()
    canvas.draw()
    tree_predicted.delete(*tree_predicted.get_children())
    for year, turnover in zip(forecast_years, median):
        tree_predicted.insert('', 'end', values=(year, f"{turnover/1000000:.2f}"))
    insert_predicted_data(forecast_years, median)
    prediction_made = True
    predict_button.config(state=tk.DISABLED)

def insert_predicted_data(forecast_years, predicted_turnovers):
    try:
        with mydb.cursor() as mycursor:
            mycursor.execute("DELETE FROM predicted_turnover")
            print(f"Cleared existing predictions.")
            sql = "INSERT INTO predicted_turnover (year, Predicted_turnover) VALUES (%s, %s)"
            val = [(int(year), float(turnover)) for year, turnover in zip(forecast_years, predicted_turnovers)]
            mycursor.executemany(sql, val)
            print(f"Inserted {len(val)} new predictions.")
            mydb.commit()
            print("Prediction data inserted successfully.")
    except ms.Error as e:
        print(f"Error inserting predictions: {e}")
        mydb.rollback()

def reprocess():
    global actual_data, estimated_data, prediction_made
    try:
        with mydb.cursor() as mycursor:
            mycursor.execute("DELETE FROM predicted_turnover")
            print(f"Cleared {mycursor.rowcount} predictions from the database.")
            mycursor.execute("DELETE FROM year_on_year WHERE year >= YEAR(CURDATE()) ")
            print(f"Cleared {mycursor.rowcount} predictions from the database.")
            mycursor.execute("UPDATE year_on_year SET SFLAG = 0")
            print(f"Reset SFLAG for {mycursor.rowcount} entries.")
            mydb.commit()
        result = fetch_data()
        actual_data = [(row[0], row[1]) for row in result]
        estimated_data = []
        update_plot()
        update_table()
        tree_predicted.delete(*tree_predicted.get_children())
        prediction_made = False
        predict_button.config(state=tk.NORMAL)
        messagebox.showinfo("Reprocess", "All estimated and predicted data has been cleared.")
    except ms.Error as e:
        print(f"Error during reprocess: {e}")
        mydb.rollback()
        messagebox.showerror("Error", "An error occurred while reprocessing the data.")

def on_plot_click(event):
    global prediction_made
    if event.inaxes and event.button == 1 and not prediction_made:
        
        x = event.xdata
        y = event.ydata
        new_year = int(round(x))
        new_turnover = round(y*1000000 , 2) # Convert back to actual turnover value
        current_year = datetime.date.today().year
        year=fetch_data()
        if new_year==year:
            print("data for this year exists.")
        if new_year <= current_year:
            actual_data.append((new_year, new_turnover))
            insert_data_point(new_year, new_turnover)
        else:
            estimated_data.append((new_year, new_turnover))
        update_plot()
        update_table()

# Create the main window
root = tk.Tk()
root.title("Financial Analysis")
root.geometry("1400x700")

# Create frames
graph_frame = tk.Frame(root)
graph_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=False)
table_frame = tk.Frame(root)
table_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=False)
button_frame = tk.Frame(root)
button_frame.pack(side=tk.BOTTOM, fill=tk.X)

# Create the plot
fig, ax = plt.subplots(figsize=(11, 9))
canvas = FigureCanvasTkAgg(fig, master=graph_frame)
canvas_widget = canvas.get_tk_widget()
canvas_widget.pack(fill=tk.BOTH, expand=False)
toolbar = NavigationToolbar2Tk(canvas, graph_frame)
toolbar.update()
canvas_widget.pack(fill=tk.BOTH, expand=False)

# Create treeviews
tree_actual = create_editable_treeview(table_frame, ('Year', 'Turnover(in million $)'))
tree_actual.pack(side=tk.TOP, fill=tk.BOTH, expand=True)
tree_predicted = create_editable_treeview(table_frame, ('Year', 'Predicted Turnover(in million $)'))
tree_predicted.pack(side=tk.BOTTOM, fill=tk.BOTH, expand=True)

# Create buttons
reprocess_button = tk.Button(button_frame, text="Reprocess", command=reprocess)
reprocess_button.pack(side=tk.TOP, padx=5, pady=5)
prediction_frame = tk.Frame(button_frame)
prediction_frame.pack(side=tk.LEFT, padx=5, pady=6)
predict_button = tk.Button(prediction_frame, text="Predict", command=predict)
predict_button.pack(side=tk.TOP, padx=5, pady=5)
year_var = tk.StringVar(value="3")
radio_3_years = tk.Radiobutton(prediction_frame, text="3 Years", variable=year_var, value="3")
radio_5_years = tk.Radiobutton(prediction_frame, text="5 Years", variable=year_var, value="5")
radio_3_years.pack(side=tk.LEFT)
radio_5_years.pack(side=tk.LEFT)

# Connect the event handler to the figure
fig.canvas.mpl_connect('button_press_event', on_plot_click)

# Initialize the database connection
mydb = connect_to_database()
if not mydb:
    root.destroy()
    exit(1)

# Initialize the display
def initialize_display():
    global actual_data, estimated_data
    result = fetch_data()
    actual_data = [(row[0], row[1]) for row in result]
    estimated_data = []
    update_plot()
    update_table()

initialize_display()

# Start the main event loop
root.mainloop()

mydb.close()