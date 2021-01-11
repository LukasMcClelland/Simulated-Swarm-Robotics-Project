Swarm Robot Path Discovery and Optimization

This project was completed for the COMP-4905 class at Carleton University. It's an honours project that was completed under the supervision and guidance of Professor Mark Lanthier. We collaborated on the ideas and goals of the project. I wrote all of the source code and the PDF report. The project was given an A+ by Prof. Lanthier. 

To run the program:
1. Clone this repository.
2. Run the `install_dependencies.bat` file.
3. Run the `run_example.bat` file. This will launch a small example run through of the program. 
4. Program parameters (number of bots, communication range, environment, etc. )can be edited in line 2 of the `run_example.bat` file. 

A custom environment can be used by editing lines 880, 881, and 882 pf `main.py`. Supply your own PNG on line 880, supply y and x values for the robots starting point on line 881, and then supply y and x values for the robots ending point on line 882. NOTE: Robots can only travel along black pixels so in your PNG file. For the program to complete successfully,  there must exist at least one black pixel path between start and end points.  

Thank you for taking the time to explore my work. 
Lukas
