#Helper to colour code Variance column conditionally
##Rules:
# 1) if spent>budget, colour = green
# 2) if spent<budget and spent >= 70% of budget, colour = orange
# 3) else, colour =red 
def variance_colour_style(row):
    try:
        budget = float(row["Amount Budgeted"])
    except:
        budget = 0.0

    try:
        spent = float(row["Amount Spent (USD)"])
    except:
        spent = 0.0

    try:
        variance = float(row["Variance (USD)"])
    except:
        variance = 0.0

    # default = no styling
    styles = [""] * len(row)

    # Apply to variance column only
    if variance < 0:
        colour = "background-color: #8B0000; color: white;" #red
    elif variance > 0 and spent >= 0.7 * budget:
        colour = "background-color: orange; color: black;"  #orange
    elif variance > 0:
        colour = "background-color: #4CAF50; color: white;" #green
    else:
        colour = ""  # variance == 0
    
    try:
        index = row.index.get_loc("Variance (USD)")
        styles[index] = colour
    except Exception as e:
        print (f"An error has occured: {e}")
    return styles

#Helper function to create a status column.
def get_variance_status(budget, spent, variance):
    if variance < 0:
        return "Overspent"
    elif variance > 0 and spent >= 0.70 * budget:
        return "Warning — ≥70% Spent"
    elif variance > 0:
        return "Within Budget"
    else:
        return "No Expenditure / OOB"