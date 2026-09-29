# ASM Plan: Anaerobic EBPR Tank Modeling

## User Input
Data are located at input/data1.xlsx. Build an ASM model to simulate an anaerobic tank, including COD degradation, simplified nitrogen removal, and enhanced biological phosphorus removal. The boundary to consider is sludge return (sludge return rate coefficient is 0.5 /h, and return sludge concentration is 2 times the steady-state concentration). Calibrate readily biodegradable COD, orthophosphate, and poly-beta-hydroxyalkanoate. Please keep intermediate files and analyze the modeling process and results

## Process Identification Summary
This task models the anaerobic zone of an EBPR-integrated process as a single CSTR, emphasizing anaerobic hydrolysis, PAO-driven PHA storage with phosphate release, and simplified nitrogen transformations under return-sludge recycle.

## 1. Define Model Boundaries
modelcomplex=EBPRCODN. The 17-component/18-reaction framework is selected because the task explicitly requires enhanced biological phosphorus removal with PAO/PHA/PP dynamics and simplified nitrogen removal, not complete nitrification or N2O intermediates. The base unit is a reaction-only single CSTR; any spatial or source/sink effects are introduced only through the Step 6 boundary menu and passed into run_pipeline via the boundaries argument.

## 2. Define State Components
The enabled state vector contains 17 components: soluble species S_sub_S, S_sub_I, S_sub_NH_sub_4, S_sub_NO_sub_3, S_sub_ALK, S_sub_O_sub_2, and S_sub_PO_sub_4, plus particulate species X_sub_S, X_sub_I, X_sub_H, X_sub_STO, X_sub_PP, X_sub_PAO, and X_sub_PHA, together with the nitrogen species needed for simplified denitrification. Component names follow the asmlibrary.py convention using `_sub_X` subscript syntax.

## 3. Determine Biochemical Reactions
EBPRCODN activates hydrolysis of slowly biodegradable substrate, heterotrophic aerobic and anoxic growth and decay, simplified one-step nitrification and denitrification, PAO anaerobic storage of S_sub_S as X_sub_PHA coupled to S_sub_PO_sub_4 release, PAO aerobic/anoxic growth and decay, and polyphosphate storage and decay. These reaction classes capture COD degradation, simplified nitrogen removal, and EBPR behavior in the anaerobic tank.

## 4. Build the Stoichiometric Matrix
The stoichiometric matrix is sliced from asmlibrary.STOICHIOMETRY for the 18 active EBPRCODN reactions and 17 active components, yielding an 18-by-17 matrix in which rows correspond to process rates and columns correspond to component accumulation rates. Coefficients for COD, nitrogen, phosphorus, and charge conservation are preserved exactly as defined in asmlibrary.py.

## 5. Build Kinetic Rate Equations
Each process rate combines Monod saturation, oxygen switching, nitrate/nitrite inhibition, and PAO-related switching functions; the complete parameter definitions and algebraic rate expressions reside in asmlibrary.PARAMS and asmlibrary.RATE_EQUATIONS. Step 7 will identify the subset of parameters whose perturbations most influence the calibration targets, and Step 8 will optimize only that subset.

## 6. Build Mass-Balance Equations
The mass balance for each component is dC_i/dt = sum_j(nu_ij * rho_j) + boundary_terms(t, state, env), where the reaction term is computed from the sliced stoichiometric matrix and rate vector, and boundary_terms are supplied through the run_pipeline boundaries argument. The user explicitly specified only sludge return:

- RAS recycle boundary: k_RAS=0.5 /h, factor=2 (all X_sub_*)

## 7. Run Sensitivity Analysis with Data
Set xlsx_path=input/data1.xlsx. Run one-at-a-time parameter perturbations of plus/minus sens_delta=0.10 across asmlibrary.PARAMS for the EBPRCODN model, compute normalized sensitivities of the S_sub_S, S_sub_PO_sub_4, and X_sub_PHA trajectories, rank parameters by aggregate absolute normalized sensitivity, select the top senstopk=6 parameters, and write the sensitivity rankings and Jacobian summaries to midoutput/sensitivity.json.

## 8. Run Parameter Calibration
Set calibmode=WeightedNRMSE, sens_targets={S_sub_S: 1.0, S_sub_PO_sub_4: 1.0, X_sub_PHA: 1.0}, maxiter=120. Use the top-6 sensitivity-selected parameters as decision variables, optimize the weighted normalized RMSE across the three targets with Nelder-Mead, and write the calibrated parameter values, per-target NRMSE, and aggregate NRMSE to midoutput/calibration.json.

## 9. Interpret Calibration Results
Evaluate the per-target and aggregate NRMSE against the standard thresholds: values at or below 0.30 indicate acceptable model fit, 0.30-0.60 indicate high but still usable error, and above 0.60 indicate clearly high residual error. Document the calibrated parameter changes, the physical consistency of anaerobic COD/PHA/PO4 dynamics, and the main uncertainty drivers. The final reports are written to output/asm_report.md and output/asm_report.pdf.